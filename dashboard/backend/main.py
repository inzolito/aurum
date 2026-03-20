import sys
import os
import time as _time
import threading as _threading
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

# Añadir el root del proyecto al path para importar DBConnector
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.db_connector import DBConnector
from dashboard.backend.auth import verify_password, create_access_token, decode_access_token
from dotenv import load_dotenv

# Cargar .env local si existe
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI(title="Aurum Prism API")

# ── Cache MT5 (evita reconectar MetaAPI en cada request) ─────────────────────
_mt5_cache      = {}
_mt5_cache_ts   = 0.0
_mt5_cache_lock = _threading.Lock()
_MT5_TTL        = 5   # segundos

def _get_mt5_cuenta():
    """Lee balance/equity/pnl desde estado_bot (escrito por aurum-core cada ciclo)."""
    global _mt5_cache, _mt5_cache_ts
    now = _time.time()
    with _mt5_cache_lock:
        if now - _mt5_cache_ts < _MT5_TTL and _mt5_cache:
            return _mt5_cache
    try:
        db = DBConnector()
        if not db.conectar():
            return {}
        with db._lock:
            db.cursor.execute("SELECT balance, equity, pnl_flotante FROM estado_bot WHERE id = 1")
            row = db.cursor.fetchone()
        if not row or row[0] is None:
            return {}
        result = {
            "balance":      float(row[0]),
            "equity":       float(row[1]) if row[1] is not None else float(row[0]),
            "pnl_flotante": float(row[2]) if row[2] is not None else 0.0,
            "currency":     "USD",
        }
        with _mt5_cache_lock:
            _mt5_cache    = result
            _mt5_cache_ts = now
        return result
    except Exception:
        return {}

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción cambiar por el dominio real
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Modelos
class Token(BaseModel):
    access_token: str
    token_type: str

class UserLogin(BaseModel):
    username: str
    password: str

# Inyección de dependencia para la DB
def get_db():
    db = DBConnector()
    if not db.conectar():
        # Fallback instantáneo a localhost si falla la IP externa
        print("[PRISM] Fallo conexión inicial, intentando fallback a localhost...")
        os.environ["DB_HOST"] = "localhost"
        if not db.conectar():
             raise HTTPException(status_code=500, detail="Error de conexión: No se pudo alcanzar la DB en el servidor.")
    
    # Auto-reparación: Verificar y crear tablas prism_ si no existen
    try:
        with db._lock:
            db.cursor.execute("SELECT 1 FROM prism_usuarios LIMIT 1")
    except Exception:
        db.conn.rollback()
        print("[PRISM] Tablas prism_ no encontradas. Ejecutando auto-migración...")
        with db._lock:
            db.cursor.execute("""
                CREATE TABLE IF NOT EXISTS prism_usuarios (
                    id SERIAL PRIMARY KEY,
                    usuario VARCHAR(50) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    rol VARCHAR(20) DEFAULT 'SUPER_ADMIN',
                    estado BOOLEAN DEFAULT TRUE
                );
                CREATE TABLE IF NOT EXISTS prism_sesiones (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER,
                    token_jwt TEXT,
                    creado_en TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS prism_log_seguridad (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER,
                    evento VARCHAR(50),
                    ip_origen VARCHAR(45),
                    fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Asegurar usuario msalasm / Singluten2! usando la lógica de auth.py
            from dashboard.backend.auth import get_password_hash
            pwd_hash = get_password_hash("Singluten2!")
            db.cursor.execute("INSERT INTO prism_usuarios (usuario, password_hash) VALUES ('msalasm', %s) ON CONFLICT DO NOTHING", (pwd_hash,))
            db.conn.commit()
            print("[PRISM] Auto-migración completada con éxito.")

    try:
        yield db
    finally:
        db.desconectar()

@app.post("/api/auth/login", response_model=Token)
async def login(user_data: UserLogin, db: DBConnector = Depends(get_db)):
    # 1. Buscar usuario en prism_usuarios
    try:
        with db._lock:
            db.cursor.execute(
                "SELECT id, password_hash, rol, estado FROM prism_usuarios WHERE usuario = %s",
                (user_data.username,)
            )
            user = db.cursor.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en consulta: {str(e)}")
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    
    user_id, pwd_hash, rol, estado = user
    
    if not estado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado",
        )

    # 2. Verificar contraseña
    if not verify_password(user_data.password, pwd_hash):
        # Registrar fallo en log de seguridad
        with db._lock:
            db.cursor.execute(
                "INSERT INTO prism_log_seguridad (usuario_id, evento, ip_origen) VALUES (%s, 'FALLO_LOGIN', 'unknown')",
                (user_id,)
            )
            db.conn.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    # 3. Registrar éxito y generar token
    access_token = create_access_token(data={"sub": user_data.username, "rol": rol})
    
    with db._lock:
        # Guardar sesión
        db.cursor.execute(
            "INSERT INTO prism_sesiones (usuario_id, token_jwt) VALUES (%s, %s)",
            (user_id, access_token)
        )
        # Registrar log
        db.cursor.execute(
            "INSERT INTO prism_log_seguridad (usuario_id, evento, ip_origen) VALUES (%s, 'LOGIN_EXITOSO', 'unknown')",
            (user_id,)
        )
        db.conn.commit()

    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/dashboard/status")
async def get_dashboard_status(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    # Verificar token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    
    # Obtener datos del dashboard (usando el método existente)
    data = db.get_dashboard_data()
    from datetime import datetime
    return {"data": data, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

@app.get("/api/control/estado")
async def get_control_estado(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    result = {
        "estado": {"estado_general": "DESCONOCIDO", "pensamiento_actual": "Sin datos", "tiempo": None},
        "posiciones_abiertas": 0,
        "trades_hoy": 0,
        "pnl_hoy": 0.0,
    }

    with db._lock:
        try:
            db.cursor.execute("SELECT estado_general, pensamiento_actual, tiempo FROM estado_bot WHERE id = 1")
            row = db.cursor.fetchone()
            if row:
                result["estado"] = {
                    "estado_general": row[0],
                    "pensamiento_actual": row[1],
                    "tiempo": row[2].isoformat() if row[2] else None,
                }
                result["estado_bot_tiempo"] = row[2].isoformat() if row[2] else None
        except Exception:
            db.conn.rollback()

        try:
            db.cursor.execute("SELECT COUNT(*) FROM registro_operaciones WHERE resultado_final IS NULL AND ticket_mt5 != 999999")
            result["posiciones_abiertas"] = db.cursor.fetchone()[0] or 0
        except Exception:
            db.conn.rollback()

        try:
            db.cursor.execute("SELECT numero_version, descripcion FROM versiones_sistema WHERE estado = 'ACTIVA' ORDER BY id DESC LIMIT 1")
            vrow = db.cursor.fetchone()
            result["version"] = vrow[0] if vrow else "v1.0.0"
            result["version_desc"] = vrow[1] if vrow else ""
        except Exception:
            db.conn.rollback()
            result["version"] = "v1.0.0"
            result["version_desc"] = ""

        try:
            db.cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(pnl_usd), 0)
                FROM registro_operaciones
                WHERE DATE(tiempo_entrada) = CURRENT_DATE
            """)
            row = db.cursor.fetchone()
            if row:
                result["trades_hoy"] = row[0] or 0
                result["pnl_hoy"] = float(row[1] or 0)
        except Exception:
            db.conn.rollback()

    # Balance/equity desde estado_bot (escrito por el bot cada ciclo)
    cuenta = _get_mt5_cuenta()
    result["balance"]  = cuenta.get("balance")
    result["equity"]   = cuenta.get("equity")
    result["currency"] = cuenta.get("currency", "USD")

    # PnL flotante = equity - balance (más fiable: pnl_flotante en BD siempre viene 0)
    equity  = cuenta.get("equity",  0) or 0
    balance = cuenta.get("balance", 0) or 0
    result["pnl_flotante"] = round(equity - balance, 2)

    return result


@app.get("/api/control/posiciones")
async def get_control_posiciones(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    with db._lock:
        try:
            db.cursor.execute("""
                SELECT a.simbolo, ro.ticket_mt5, ro.tipo_orden, ro.volumen_lotes,
                       ro.precio_entrada, ro.stop_loss, ro.take_profit,
                       ro.pnl_usd, ro.tiempo_entrada, ro.justificacion_entrada,
                       ro.veredicto_apertura, ro.probabilidad_est,
                       ro.precio_actual
                FROM registro_operaciones ro
                JOIN activos a ON a.id = ro.activo_id
                WHERE ro.resultado_final IS NULL AND ro.ticket_mt5 != 999999
                ORDER BY ro.tiempo_entrada DESC
            """)
            cols = ["simbolo", "ticket", "tipo", "lotes", "precio_entrada", "sl", "tp",
                    "pnl_usd", "apertura", "justificacion_entrada", "veredicto", "probabilidad",
                    "precio_actual"]
            rows = db.cursor.fetchall()
            posiciones = []
            import json as _json
            for r in rows:
                d = dict(zip(cols, r))
                if d.get("apertura"):
                    d["apertura"] = d["apertura"].isoformat()
                # Parsear justificacion JSON si existe
                raw = d.pop("justificacion_entrada", None)
                if raw:
                    try:
                        d["analisis"] = _json.loads(raw)
                    except Exception:
                        d["analisis"] = {"ia_texto": raw}
                posiciones.append(d)
            return {"posiciones": posiciones}
        except Exception:
            db.conn.rollback()
            return {"posiciones": []}


@app.get("/api/control/logs")
async def get_control_logs(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    with db._lock:
        try:
            db.cursor.execute("""
                SELECT nivel, modulo, mensaje, tiempo
                FROM log_sistema
                ORDER BY tiempo DESC
                LIMIT 100
            """)
            rows = db.cursor.fetchall()
            return {"logs": [
                {"nivel": r[0], "modulo": r[1], "mensaje": r[2],
                 "tiempo": r[3].isoformat() if r[3] else None}
                for r in rows
            ]}
        except Exception:
            db.conn.rollback()
            return {"logs": []}


@app.get("/api/noticias")
async def get_noticias(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    with db._lock:
        try:
            db.cursor.execute("""
                SELECT title, source, content_summary, timestamp, published_at
                FROM raw_news_feed
                ORDER BY published_at DESC NULLS LAST
                LIMIT 150
            """)
            rows = db.cursor.fetchall()

            # Cargar razonamientos recientes de Gemini por activo
            db.cursor.execute("""
                SELECT DISTINCT ON (activo_id)
                    a.simbolo, sn.razonamiento_ia, sn.impacto_nlp, sn.tiempo
                FROM sentimiento_noticias sn
                JOIN activos a ON a.id = sn.activo_id
                ORDER BY activo_id, sn.tiempo DESC
            """)
            razonamientos = {r[0]: {"razonamiento": r[1], "nlp": float(r[2]), "tiempo": r[3].isoformat() if r[3] else None}
                             for r in db.cursor.fetchall()}

            noticias = []
            for r in rows:
                title, source, summary, ts, pub_at = r
                impacto = None
                tipo = "filtrada"
                url = None
                if summary:
                    partes = summary.split("|")
                    if len(partes) >= 2:
                        url = partes[-1].strip()
                    if "Impacto:" in summary:
                        try:
                            impacto = int(partes[0].replace("Impacto:", "").strip().split("/")[0])
                            tipo = "relevante"
                        except Exception:
                            pass
                    elif "Descargada" in summary:
                        tipo = "descartada"
                noticias.append({
                    "titulo": title,
                    "fuente": source,
                    "impacto": impacto,
                    "tipo": tipo,
                    "url": url,
                    "timestamp": ts.isoformat() if ts else None,
                    "published_at": pub_at.isoformat() if pub_at else None,
                })
            return {"noticias": noticias, "total": len(noticias), "razonamientos": razonamientos}
        except Exception:
            db.conn.rollback()
            return {"noticias": [], "total": 0, "razonamientos": {}}


@app.post("/api/control/sync-mt5")
async def sync_mt5(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    import asyncio, os
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "sync_operaciones.py"))

    if not os.path.exists(script):
        raise HTTPException(status_code=500, detail=f"Script no encontrado: {script}")

    python = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "venv", "bin", "python"))
    if not os.path.exists(python):
        python = sys.executable

    try:
        proc = await asyncio.create_subprocess_exec(
            python, script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode(errors="replace")
        ok = proc.returncode == 0
        return {"status": "ok" if ok else "error", "output": output}
    except asyncio.TimeoutError:
        return {"status": "timeout", "output": "La sincronización tardó más de 2 minutos."}
    except Exception as e:
        return {"status": "error", "output": str(e)}


@app.post("/api/control/deploy")
async def deploy(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    import asyncio, os
    script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "update.sh")
    script = os.path.abspath(script)

    if not os.path.exists(script):
        raise HTTPException(status_code=500, detail=f"Script no encontrado: {script}")

    try:
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        output = stdout.decode(errors="replace")
        ok = proc.returncode == 0

        # Auto-restart del dashboard en background (2s de delay para enviar respuesta)
        if ok:
            async def _restart_self():
                await asyncio.sleep(2)
                import subprocess
                subprocess.Popen(["sudo", "systemctl", "restart", "aurum-dashboard"])
            asyncio.create_task(_restart_self())

        return {"status": "ok" if ok else "error", "output": output, "returncode": proc.returncode}
    except asyncio.TimeoutError:
        return {"status": "timeout", "output": "El deploy tardó más de 3 minutos.", "returncode": -1}
    except Exception as e:
        return {"status": "error", "output": str(e), "returncode": -1}


@app.get("/api/mercado/pulso")
async def mercado_pulso(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    try:
        db.cursor.execute("""
            SELECT DISTINCT ON (a.id)
                a.simbolo_broker            AS simbolo,
                rs.voto_final_ponderado     AS veredicto,
                rs.decision_gerente         AS decision,
                rs.tiempo                   AS tiempo
            FROM activos a
            LEFT JOIN registro_senales rs ON rs.activo_id = a.id
            WHERE a.estado_operativo = 'ACTIVO'
            ORDER BY a.id, rs.tiempo DESC NULLS LAST
        """)
        rows = db.cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "simbolo":   r[0],
                "veredicto": float(r[1]) if r[1] is not None else None,
                "decision":  r[2],
                "tiempo":    r[3].isoformat() if r[3] else None,
            })
        return {"activos": result}
    except Exception as e:
        return {"activos": [], "error": str(e)}


@app.get("/api/historial")
async def get_historial(
    token: str = Depends(oauth2_scheme),
    db: DBConnector = Depends(get_db),
    limit: int = 200,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    simbolo: Optional[str] = None,
    resultado: Optional[str] = None,
):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    with db._lock:
        try:
            conditions = ["(ro.resultado_final IS NOT NULL OR ro.ticket_mt5 = 999999)"]
            params: list = []
            if desde:
                conditions.append("(ro.tiempo_entrada AT TIME ZONE 'America/Santiago')::date >= %s::date")
                params.append(desde)
            if hasta:
                conditions.append("(ro.tiempo_entrada AT TIME ZONE 'America/Santiago')::date <= %s::date")
                params.append(hasta)
            if simbolo:
                conditions.append("a.simbolo = %s")
                params.append(simbolo)
            if resultado:
                conditions.append("ro.resultado_final = %s")
                params.append(resultado.upper())
            where = " AND ".join(conditions)
            params.append(limit)
            db.cursor.execute(f"""
                SELECT a.simbolo, ro.ticket_mt5, ro.tipo_orden, ro.volumen_lotes,
                       ro.precio_entrada, ro.stop_loss, ro.take_profit,
                       ro.pnl_usd, ro.tiempo_entrada, ro.resultado_final,
                       ro.veredicto_apertura, ro.probabilidad_est, ro.divergencia_precision,
                       ro.justificacion_entrada,
                       ap.tipo_fallo, ap.worker_culpable, ap.descripcion, ap.correccion_sugerida,
                       vs.numero_version
                FROM registro_operaciones ro
                JOIN activos a ON a.id = ro.activo_id
                LEFT JOIN (
                    SELECT DISTINCT ON (ticket_mt5) *
                    FROM autopsias_perdidas
                    ORDER BY ticket_mt5, id DESC
                ) ap ON ap.ticket_mt5 = ro.ticket_mt5
                LEFT JOIN versiones_sistema vs ON vs.id = ro.version_id
                WHERE {where}
                ORDER BY ro.tiempo_entrada DESC
                LIMIT %s
            """, params)
            cols = ["simbolo", "ticket", "tipo", "lotes", "precio_entrada", "sl", "tp",
                    "pnl_usd", "apertura", "resultado", "veredicto", "probabilidad",
                    "divergencia", "justificacion_entrada",
                    "tipo_fallo", "worker_culpable", "descripcion_fallo", "correccion",
                    "version"]
            rows = db.cursor.fetchall()
            import json as _json
            trades = []
            for r in rows:
                d = dict(zip(cols, r))
                if d.get("apertura"):
                    d["apertura"] = d["apertura"].isoformat()
                for k in ["pnl_usd", "veredicto", "probabilidad", "divergencia"]:
                    if d[k] is not None:
                        d[k] = float(d[k])
                raw = d.pop("justificacion_entrada", None)
                if raw:
                    try:
                        d["analisis"] = _json.loads(raw)
                    except Exception:
                        d["analisis"] = {"ia_texto": raw}
                trades.append(d)
            return {"trades": trades}
        except Exception as e:
            db.conn.rollback()
            return {"trades": [], "error": str(e)}


@app.post("/api/control/restart-bot")
async def restart_bot(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "restart", "aurum-core", "aurum-hunter", "aurum-telegram",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = stdout.decode(errors="replace") or "Servicios reiniciados."
        return {"status": "ok" if proc.returncode == 0 else "error", "output": output}
    except Exception as e:
        return {"status": "error", "output": str(e)}


@app.post("/api/control/test-bot")
async def test_bot(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "is-active", "aurum-core", "aurum-hunter", "aurum-telegram",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        lines = stdout.decode(errors="replace").strip().splitlines()
        services = ["aurum-core", "aurum-hunter", "aurum-telegram"]
        result = {s: (lines[i] if i < len(lines) else "unknown") for i, s in enumerate(services)}
        all_ok = all(v == "active" for v in result.values())
        return {"status": "ok" if all_ok else "degraded", "services": result}
    except Exception as e:
        return {"status": "error", "services": {}, "output": str(e)}


@app.get("/api/config/parametros")
async def get_parametros(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    try:
        with db._lock:
            db.cursor.execute("""
                SELECT modulo, nombre_parametro, valor, descripcion
                FROM parametros_sistema
                ORDER BY modulo, nombre_parametro
            """)
            rows = db.cursor.fetchall()
        return {"parametros": [
            {"modulo": r[0], "nombre": r[1], "valor": float(r[2]), "descripcion": r[3] or ""}
            for r in rows
        ]}
    except Exception as e:
        db.conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


_PARAM_RANGOS = {
    "GERENTE.umbral_disparo":   (0.10, 0.90),
    "GERENTE.riesgo_trade_pct": (0.10, 5.00),
    "GERENTE.ratio_tp":         (1.00, 5.00),
    "GERENTE.sl_atr_mult":      (0.50, 4.00),
    "GERENTE.max_drawdown_pct": (1.0,  20.0),
    "TENDENCIA.peso_voto":      (0.05, 0.80),
    "NLP.peso_voto":            (0.05, 0.80),
    "ORDER_FLOW.peso_voto":     (0.00, 0.80),
    "SNIPER.peso_voto":         (0.00, 0.80),
}

class ParamUpdate(BaseModel):
    nombre: str
    valor: float

@app.put("/api/config/parametros")
async def update_parametro(body: ParamUpdate, token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    if body.nombre in _PARAM_RANGOS:
        min_v, max_v = _PARAM_RANGOS[body.nombre]
        if not (min_v <= body.valor <= max_v):
            raise HTTPException(status_code=422, detail=f"{body.nombre} debe estar entre {min_v} y {max_v}")
    try:
        with db._lock:
            db.cursor.execute(
                "UPDATE parametros_sistema SET valor = %s WHERE nombre_parametro = %s",
                (str(body.valor), body.nombre)
            )
            if db.cursor.rowcount == 0:
                # Si no existe, insertarlo (nuevo parámetro)
                modulo = body.nombre.split(".")[0] if "." in body.nombre else "GERENTE"
                db.cursor.execute(
                    "INSERT INTO parametros_sistema (modulo, nombre_parametro, valor) VALUES (%s, %s, %s)",
                    (modulo, body.nombre, str(body.valor))
                )
            db.conn.commit()
        # Invalida caché del bot (próximo ciclo releerá la BD)
        db._params_last_refresh = 0
        return {"ok": True, "nombre": body.nombre, "valor": body.valor}
    except Exception as e:
        db.conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "operational", "version": "Prism 1.0"}


# ── Servir frontend compilado (SPA) ──────────────────────────────────────────
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(_dist):
    _assets = os.path.join(_dist, "assets")
    if os.path.exists(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/favicon.svg")
    async def favicon():
        return FileResponse(os.path.join(_dist, "favicon.svg"), media_type="image/svg+xml")

    @app.get("/{full_path:path}")
    async def spa_handler(full_path: str):
        return FileResponse(os.path.join(_dist, "index.html"))
else:
    print("[PRISM] Frontend no compilado. Corre: cd dashboard/frontend && npm run build")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
