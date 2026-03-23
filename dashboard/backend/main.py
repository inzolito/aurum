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

# ── Filtro global de versión (solo mostrar datos desde V17.01 en adelante) ───
_FILTRO_VERSION_MINIMA = 17.01
_filtro_version_id_cache: Optional[int] = None

def _version_min_id(cursor) -> int:
    """Retorna el version_id mínimo (de versiones_sistema) para versiones >= V17.01. Cacheado."""
    global _filtro_version_id_cache
    if _filtro_version_id_cache is None:
        try:
            cursor.execute("""
                SELECT MIN(id) FROM versiones_sistema
                WHERE CAST(REGEXP_REPLACE(REPLACE(UPPER(numero_version), 'V', ''), '[^0-9.]', '', 'g') AS NUMERIC) >= %s
            """, (_FILTRO_VERSION_MINIMA,))
            row = cursor.fetchone()
            _filtro_version_id_cache = int(row[0]) if row and row[0] else 1
        except Exception:
            _filtro_version_id_cache = 1
    return _filtro_version_id_cache

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
            min_ver = _version_min_id(db.cursor)
            conditions = ["(ro.resultado_final IS NOT NULL OR ro.ticket_mt5 = 999999)", "ro.version_id >= %s"]
            params: list = [min_ver]
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


@app.get("/api/config/activos")
async def get_activos(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    with db._lock:
        try:
            db.cursor.execute("""
                SELECT a.id, a.simbolo, a.nombre, a.categoria, a.estado_operativo,
                    COUNT(ro.id) FILTER (WHERE ro.resultado_final IS NOT NULL) as trades,
                    COUNT(ro.id) FILTER (WHERE ro.resultado_final = 'GANADO') as ganados,
                    COUNT(ro.id) FILTER (WHERE ro.resultado_final = 'PERDIDO') as perdidos,
                    ROUND(COALESCE(SUM(ro.pnl_usd) FILTER (WHERE ro.resultado_final IS NOT NULL), 0)::numeric, 2) as pnl_total
                FROM activos a
                LEFT JOIN registro_operaciones ro ON ro.activo_id = a.id
                LEFT JOIN versiones_sistema vs ON vs.id = ro.version_id
                WHERE ro.id IS NULL OR ro.version_id >= %s
                GROUP BY a.id, a.simbolo, a.nombre, a.categoria, a.estado_operativo
                ORDER BY a.estado_operativo, a.simbolo
            """, (_version_min_id(db.cursor),))
            rows = db.cursor.fetchall()
        except Exception as e:
            db.conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    return {"activos": [
        {"id": r[0], "simbolo": r[1], "nombre": r[2], "categoria": r[3],
         "estado": r[4], "trades": int(r[5]), "ganados": int(r[6]), "perdidos": int(r[7]), "pnl_total": float(r[8])}
        for r in rows
    ]}


class ActivoUpdate(BaseModel):
    estado: str

@app.put("/api/config/activos/{simbolo}")
async def update_activo(simbolo: str, body: ActivoUpdate, token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    estados_validos = ("ACTIVO", "LABORATORIO", "INACTIVO", "SOLO_LECTURA")
    if body.estado not in estados_validos:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Opciones: {estados_validos}")
    with db._lock:
        try:
            db.cursor.execute(
                "UPDATE activos SET estado_operativo = %s WHERE simbolo = %s",
                (body.estado, simbolo.upper())
            )
            db.conn.commit()
        except Exception as e:
            db.conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "simbolo": simbolo.upper(), "estado": body.estado}


@app.get("/api/config/activos/{simbolo}/rendimiento")
async def get_rendimiento_activo(simbolo: str, token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    with db._lock:
        try:
            # Resumen por versión del bot
            db.cursor.execute("""
                SELECT
                    COALESCE(vs.nombre, 'Sin versión') as version,
                    COUNT(ro.id) as trades,
                    COUNT(ro.id) FILTER (WHERE ro.resultado_final = 'GANADO') as ganados,
                    COUNT(ro.id) FILTER (WHERE ro.resultado_final = 'PERDIDO') as perdidos,
                    ROUND(COALESCE(SUM(ro.pnl_usd) FILTER (WHERE ro.resultado_final IS NOT NULL), 0)::numeric, 2) as pnl,
                    ROUND(COALESCE(AVG(ro.pnl_usd) FILTER (WHERE ro.resultado_final = 'GANADO'), 0)::numeric, 2) as avg_win,
                    ROUND(COALESCE(AVG(ro.pnl_usd) FILTER (WHERE ro.resultado_final = 'PERDIDO'), 0)::numeric, 2) as avg_loss
                FROM registro_operaciones ro
                JOIN activos a ON a.id = ro.activo_id
                LEFT JOIN versiones_sistema vs ON vs.id = ro.version_id
                WHERE a.simbolo = %s AND ro.resultado_final IS NOT NULL AND ro.version_id >= %s
                GROUP BY COALESCE(vs.nombre, 'Sin versión')
                ORDER BY pnl DESC
            """, (simbolo.upper(), _version_min_id(db.cursor)))
            por_version = db.cursor.fetchall()

            # Últimos 10 trades
            db.cursor.execute("""
                SELECT ro.tiempo_entrada, ro.tiempo_cierre, ro.direccion,
                       ro.precio_entrada, ro.precio_cierre, ro.pnl_usd, ro.resultado_final,
                       COALESCE(vs.nombre, '—') as version
                FROM registro_operaciones ro
                JOIN activos a ON a.id = ro.activo_id
                LEFT JOIN versiones_sistema vs ON vs.id = ro.version_id
                WHERE a.simbolo = %s AND ro.version_id >= %s
                ORDER BY ro.tiempo_entrada DESC LIMIT 10
            """, (simbolo.upper(), _version_min_id(db.cursor)))
            ultimos = db.cursor.fetchall()
        except Exception as e:
            db.conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    return {
        "simbolo": simbolo.upper(),
        "por_version": [
            {"version": r[0], "trades": int(r[1]), "ganados": int(r[2]), "perdidos": int(r[3]),
             "pnl": float(r[4]), "avg_win": float(r[5]), "avg_loss": float(r[6])}
            for r in por_version
        ],
        "ultimos_trades": [
            {"entrada": r[0].isoformat() if r[0] else None,
             "cierre": r[1].isoformat() if r[1] else None,
             "direccion": r[2], "precio_entrada": float(r[3] or 0),
             "precio_cierre": float(r[4] or 0) if r[4] else None,
             "pnl": float(r[5] or 0) if r[5] else None,
             "resultado": r[6], "version": r[7]}
            for r in ultimos
        ],
    }


@app.get("/api/monitor")
async def get_monitor(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    import psutil, subprocess
    from datetime import datetime, timezone

    result = {}
    ahora = datetime.now(timezone.utc)

    # ── 1. RAM, Swap, CPU, Disco ──────────────────────────────────────────────
    mem   = psutil.virtual_memory()
    swap  = psutil.swap_memory()
    disk  = psutil.disk_usage('/')
    cpu_pct = psutil.cpu_percent(interval=0.5)
    # Tamaño BD desde PostgreSQL
    db_size_mb = 0
    with db._lock:
        try:
            db.cursor.execute("SELECT pg_database_size(current_database())")
            r = db.cursor.fetchone()
            db_size_mb = round(r[0] / 1024**2, 1) if r else 0
        except Exception:
            db.conn.rollback()
    # Desglose de disco por directorio/log
    def _du_mb(path):
        try:
            r = subprocess.run(["du", "-sb", path], capture_output=True, text=True, timeout=5)
            return round(int(r.stdout.split()[0]) / 1024**2, 1) if r.returncode == 0 else 0
        except Exception:
            return 0

    def _count_files(path, ext):
        try:
            import glob as _glob
            return len(_glob.glob(f"{path}/**/*{ext}", recursive=True))
        except Exception:
            return 0

    journal_mb    = _du_mb("/var/log/journal")
    syslog_mb     = _du_mb("/var/log/syslog")
    telemetria_mb = _du_mb("/opt/aurum/temp/telemetry")
    telemetria_n  = _count_files("/opt/aurum/temp/telemetry", ".png")
    venv_mb       = _du_mb("/opt/aurum/venv")
    git_mb        = _du_mb("/opt/aurum/.git")
    frontend_mb   = _du_mb("/opt/aurum/dashboard/frontend")

    # Cuánto se podría liberar (journals >50MB son archivados y borrables, syslog casi todo)
    journal_ahorro  = max(0, round(journal_mb - 50, 1))   # mantener 50 MB activos
    syslog_ahorro   = max(0, round(syslog_mb  - 5,  1))   # mantener 5 MB
    telemetria_ahorro = telemetria_mb                      # todos son borrables

    result["sistema"] = {
        "ram":  {"total_mb": round(mem.total  / 1024**2), "usado_mb": round(mem.used      / 1024**2), "libre_mb": round(mem.available / 1024**2), "pct": round(mem.percent,  1)},
        "swap": {"total_mb": round(swap.total / 1024**2), "usado_mb": round(swap.used     / 1024**2), "libre_mb": round((swap.total - swap.used) / 1024**2), "pct": round(swap.percent, 1)},
        "cpu":  {"pct": round(cpu_pct, 1)},
        "disco": {"total_gb": round(disk.total / 1024**3, 1), "usado_gb": round(disk.used / 1024**3, 1), "libre_gb": round(disk.free / 1024**3, 1), "pct": round(disk.percent, 1)},
        "db_size_mb": db_size_mb,
        "disco_desglose": [
            {"item": "Logs systemd (journal)", "mb": journal_mb,    "ahorro_mb": journal_ahorro,   "accion": "Limpiar journals",          "fijo": False},
            {"item": "Syslog",                 "mb": syslog_mb,     "ahorro_mb": syslog_ahorro,    "accion": "Truncar syslog",            "fijo": False},
            {"item": "Telemetría (PNGs)",      "mb": telemetria_mb, "ahorro_mb": telemetria_ahorro,"accion": f"Borrar {telemetria_n} PNGs","fijo": False},
            {"item": "Base de datos",          "mb": db_size_mb,    "ahorro_mb": 0,                "accion": "Archivar señales viejas",   "fijo": False},
            {"item": "Entorno Python (venv)",  "mb": venv_mb,       "ahorro_mb": 0,                "accion": None,                        "fijo": True},
            {"item": "Frontend compilado",     "mb": frontend_mb,   "ahorro_mb": 0,                "accion": None,                        "fijo": True},
            {"item": "Git history (.git)",     "mb": git_mb,        "ahorro_mb": 0,                "accion": "git gc --aggressive",       "fijo": False},
        ],
    }

    # ── 2. Procesos — via systemctl (fuente de verdad, no psutil) ────────────
    _servicios = {
        "core":     "aurum-core",
        "shield":   "aurum-shield",
        "hunter":   "aurum-hunter",
        "telegram": "aurum-telegram",
    }

    def _systemctl_info(svc):
        try:
            p = subprocess.run(
                ["systemctl", "show", svc,
                 "--property=ActiveState,SubState,MainPID,ExecMainStartTimestamp,NRestarts"],
                capture_output=True, text=True, timeout=5
            )
            info = {}
            for line in p.stdout.strip().splitlines():
                if '=' in line:
                    k, v = line.split('=', 1)
                    info[k] = v
            active = info.get('ActiveState', 'unknown')
            sub    = info.get('SubState', '')
            pid    = int(info.get('MainPID', 0)) or None
            ts     = info.get('ExecMainStartTimestamp', '')
            uptime_s = 0
            if ts and ts not in ('', 'n/a'):
                try:
                    # Formato: "Sun 2026-03-22 23:52:37 UTC"
                    from datetime import datetime as _dt
                    partes = ts.split()
                    dt_str = f"{partes[1]} {partes[2]}"
                    start  = _dt.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    uptime_s = max(0, int((_dt.utcnow() - start).total_seconds()))
                except Exception:
                    pass
            nreinicios = int(info.get('NRestarts', 0))
            return {
                "vivo":      active == "active" and sub == "running",
                "estado_svc": f"{active}/{sub}",
                "pid":       pid,
                "uptime_s":  uptime_s,
                "reinicios": nreinicios,
            }
        except Exception:
            return {"vivo": False, "estado_svc": "error", "pid": None, "uptime_s": 0, "reinicios": 0}

    procesos = {k: _systemctl_info(svc) for k, svc in _servicios.items()}
    result["procesos"] = procesos

    # ── 3. Reinicios del servicio aurum-core ──────────────────────────────────
    result["reinicios"] = procesos.get("core", {}).get("reinicios", -1)

    # ── 4. Estado bot (heartbeat + balance) ───────────────────────────────────
    with db._lock:
        try:
            db.cursor.execute("SELECT tiempo, estado_general, balance, equity, pnl_flotante, pensamiento_actual FROM estado_bot WHERE id = 1")
            row = db.cursor.fetchone()
        except Exception:
            db.conn.rollback()
            row = None
    if row:
        result["bot"] = {
            "ultimo_latido": row[0].isoformat(),
            "segundos_inactivo": int((ahora - row[0]).total_seconds()),
            "estado": row[1], "balance": float(row[2] or 0),
            "equity": float(row[3] or 0), "pnl_flotante": float(row[4] or 0),
            "mensaje": row[5],
        }
    else:
        result["bot"] = None

    # ── 5. Últimas 25 señales (V17.01+) ──────────────────────────────────────
    min_ver = _version_min_id(db.cursor)
    with db._lock:
        try:
            db.cursor.execute("""
                SELECT rs.tiempo, a.simbolo, rs.decision_gerente, rs.voto_final_ponderado,
                       rs.motivo, rs.voto_tendencia, rs.voto_nlp, rs.voto_sniper,
                       rs.voto_hurst, rs.voto_macro
                FROM registro_senales rs
                JOIN activos a ON a.id = rs.activo_id
                WHERE rs.version_id >= %s
                ORDER BY rs.tiempo DESC LIMIT 25
            """, (min_ver,))
            rows = db.cursor.fetchall()
        except Exception:
            db.conn.rollback()
            rows = []
    result["senales"] = [{"tiempo": r[0].isoformat(), "simbolo": r[1], "decision": r[2],
                           "veredicto": round(float(r[3] or 0), 3), "motivo": r[4],
                           "trend": round(float(r[5] or 0), 2), "nlp": round(float(r[6] or 0), 2),
                           "sniper": round(float(r[7] or 0), 2),
                           "hurst": round(float(r[8] or 0), 2), "macro": round(float(r[9] or 0), 2)} for r in rows]

    # ── 6. Último voto por activo activo + umbral ─────────────────────────────
    with db._lock:
        try:
            db.cursor.execute("""
                SELECT DISTINCT ON (a.simbolo)
                    a.simbolo, rs.voto_tendencia, rs.voto_nlp, rs.voto_sniper,
                    rs.voto_volume, rs.voto_cross, rs.decision_gerente, rs.tiempo,
                    rs.voto_final_ponderado, rs.voto_hurst, rs.voto_macro
                FROM registro_senales rs
                JOIN activos a ON a.id = rs.activo_id
                WHERE a.estado_operativo = 'ACTIVO'
                ORDER BY a.simbolo, rs.tiempo DESC
            """)
            rows = db.cursor.fetchall()
        except Exception:
            db.conn.rollback()
            rows = []

    # Leer umbral de disparo desde BD
    umbral = 0.45
    with db._lock:
        try:
            db.cursor.execute("SELECT valor FROM parametros_sistema WHERE nombre_parametro = 'GERENTE.umbral_disparo'")
            r = db.cursor.fetchone()
            if r:
                umbral = round(float(r[0]), 3)
        except Exception:
            db.conn.rollback()

    result["umbral_disparo"] = umbral
    result["votos_workers"] = [{"simbolo": r[0], "trend": round(float(r[1] or 0), 2),
                                  "nlp": round(float(r[2] or 0), 2), "sniper": round(float(r[3] or 0), 2),
                                  "volumen": round(float(r[4] or 0), 2), "cross": round(float(r[5] or 0), 2),
                                  "decision": r[6], "tiempo": r[7].isoformat(),
                                  "veredicto": round(float(r[8] or 0), 3),
                                  "hurst": round(float(r[9] or 0), 2), "macro": round(float(r[10] or 0), 2)} for r in rows]

    # ── 7. Rendimiento hoy (hora Chile) ───────────────────────────────────────
    with db._lock:
        try:
            db.cursor.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE resultado_final IS NOT NULL),
                    COUNT(*) FILTER (WHERE resultado_final = 'GANADO'),
                    COUNT(*) FILTER (WHERE resultado_final = 'PERDIDO'),
                    COALESCE(SUM(pnl_usd) FILTER (WHERE resultado_final IS NOT NULL), 0),
                    COUNT(*) FILTER (WHERE resultado_final IS NULL AND estado = 'ABIERTA')
                FROM registro_operaciones
                WHERE (tiempo_entrada AT TIME ZONE 'America/Santiago')::date =
                      (NOW() AT TIME ZONE 'America/Santiago')::date
            """)
            r = db.cursor.fetchone()
            result["hoy"] = {"total": int(r[0]), "ganados": int(r[1]), "perdidos": int(r[2]),
                              "pnl": round(float(r[3]), 2), "abiertas": int(r[4])}
        except Exception:
            db.conn.rollback()
            result["hoy"] = {"total": 0, "ganados": 0, "perdidos": 0, "pnl": 0.0, "abiertas": 0}

    # ── 8. Estado activos no-ACTIVO (labs voluntarios + pausados reales) ────────
    with db._lock:
        try:
            db.cursor.execute("""
                SELECT a.simbolo, a.estado_operativo,
                       STRING_AGG(DISTINCT l.nombre, ', ') AS labs
                FROM activos a
                LEFT JOIN lab_activos la ON la.activo_id = a.id AND la.estado = 'ACTIVO'
                LEFT JOIN laboratorios l ON l.id = la.lab_id
                WHERE a.estado_operativo != 'ACTIVO'
                GROUP BY a.simbolo, a.estado_operativo
                ORDER BY a.simbolo
            """)
            rows = db.cursor.fetchall()
            result["activos_estado"] = [{"simbolo": r[0], "estado": r[1], "labs": r[2]} for r in rows]
        except Exception:
            db.conn.rollback()
            result["activos_estado"] = []
    # Alias de compatibilidad
    result["activos_problema"] = result["activos_estado"]

    return result


@app.get("/api/lab")
async def get_lab(token: str = Depends(oauth2_scheme), db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    import json as _json

    laboratorios = []
    with db._lock:
        try:
            db.cursor.execute("""
                SELECT l.id, l.nombre, l.categoria, l.estado,
                       l.capital_virtual, l.balance_virtual, l.creado_en, l.notas,
                       COALESCE(l.version, '1.0.0') as version
                FROM laboratorios l
                ORDER BY l.id
            """)
            labs_rows = db.cursor.fetchall()
        except Exception as e:
            db.conn.rollback()
            labs_rows = []

    for r in labs_rows:
        lab_id    = r[0]
        nombre    = r[1]
        categoria = r[2]
        estado    = r[3]
        capital   = float(r[4] or 3000)
        balance   = float(r[5] or capital)
        version   = r[8] or "1.0.0"

        # Activos del lab
        activos_lab = []
        with db._lock:
            try:
                db.cursor.execute("""
                    SELECT a.simbolo FROM lab_activos la
                    JOIN activos a ON a.id = la.activo_id
                    WHERE la.lab_id = %s AND la.estado = 'ACTIVO'
                    ORDER BY a.simbolo
                """, (lab_id,))
                activos_lab = [row[0] for row in db.cursor.fetchall()]
            except Exception:
                db.conn.rollback()

        # Métricas del lab
        metricas = {
            "trades_total": 0, "ganados": 0, "perdidos": 0,
            "win_rate": 0.0, "pnl_total": 0.0, "roe_pct": 0.0,
            "profit_factor": 0.0, "max_drawdown": 0.0,
            "avg_ganancia": 0.0, "avg_perdida": 0.0,
            "datos_suficientes": False,
        }
        with db._lock:
            try:
                db.cursor.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE estado = 'CERRADA') as total,
                        COUNT(*) FILTER (WHERE estado = 'CERRADA' AND resultado = 'TP') as ganados,
                        COUNT(*) FILTER (WHERE estado = 'CERRADA' AND resultado = 'SL') as perdidos,
                        COALESCE(SUM(pnl_virtual) FILTER (WHERE estado = 'CERRADA'), 0) as pnl_total,
                        COALESCE(AVG(pnl_virtual) FILTER (WHERE estado = 'CERRADA' AND resultado = 'TP'), 0) as avg_win,
                        COALESCE(AVG(pnl_virtual) FILTER (WHERE estado = 'CERRADA' AND resultado = 'SL'), 0) as avg_loss,
                        COALESCE(SUM(pnl_virtual) FILTER (WHERE estado = 'CERRADA' AND resultado = 'TP'), 0) as sum_win,
                        COALESCE(ABS(SUM(pnl_virtual) FILTER (WHERE estado = 'CERRADA' AND resultado = 'SL')), 0) as sum_loss
                    FROM lab_operaciones
                    WHERE lab_id = %s
                """, (lab_id,))
                mr = db.cursor.fetchone()
                if mr:
                    total = int(mr[0] or 0)
                    ganados = int(mr[1] or 0)
                    perdidos = int(mr[2] or 0)
                    pnl_total = float(mr[3] or 0)
                    avg_win = float(mr[4] or 0)
                    avg_loss = float(mr[5] or 0)
                    sum_win = float(mr[6] or 0)
                    sum_loss = float(mr[7] or 0)
                    win_rate = round((ganados / total * 100), 1) if total > 0 else 0.0
                    roe_pct = round((pnl_total / capital * 100), 2) if capital > 0 else 0.0
                    profit_factor = round(sum_win / sum_loss, 2) if sum_loss > 0 else 0.0
                    metricas = {
                        "trades_total": total,
                        "ganados": ganados,
                        "perdidos": perdidos,
                        "win_rate": win_rate,
                        "pnl_total": round(pnl_total, 2),
                        "roe_pct": roe_pct,
                        "profit_factor": profit_factor,
                        "max_drawdown": 0.0,  # Calculado aparte si hay lab_balance_diario
                        "avg_ganancia": round(avg_win, 2),
                        "avg_perdida": round(abs(avg_loss), 2),  # abs: avg_loss es negativo en BD
                        "datos_suficientes": total >= 30,
                    }
            except Exception as e:
                db.conn.rollback()

        # Operaciones recientes
        ops_recientes = []
        with db._lock:
            try:
                db.cursor.execute("""
                    SELECT lo.id, a.simbolo, lo.tipo_orden, lo.precio_entrada,
                           lo.stop_loss, lo.take_profit, lo.volumen_lotes,
                           lo.estado, lo.tiempo_entrada, lo.tiempo_salida,
                           lo.precio_salida, lo.resultado, lo.pnl_virtual, lo.roe_pct,
                           ls.voto_tendencia, ls.voto_nlp, ls.voto_sniper, ls.voto_macro,
                           ls.voto_hurst, ls.voto_volume, ls.voto_cross,
                           ls.voto_final_ponderado, ls.pesos_usados, ls.motivo,
                           lo.justificacion_entrada
                    FROM lab_operaciones lo
                    JOIN activos a ON a.id = lo.activo_id
                    LEFT JOIN lab_senales ls ON ls.id = lo.lab_senal_id
                    WHERE lo.lab_id = %s
                    ORDER BY lo.tiempo_entrada DESC
                    LIMIT 10
                """, (lab_id,))
                cols_op = ["id", "simbolo", "tipo", "precio_entrada", "sl", "tp",
                           "lotes", "estado", "entrada", "salida",
                           "precio_salida", "resultado", "pnl_virtual", "roe_pct",
                           "v_trend", "v_nlp", "v_sniper", "v_macro",
                           "v_hurst", "v_volume", "v_cross",
                           "veredicto", "pesos_usados", "motivo", "justificacion_entrada"]
                import json as _json_lab
                for op_row in db.cursor.fetchall():
                    op = dict(zip(cols_op, op_row))
                    op["entrada"] = op["entrada"].isoformat() if op["entrada"] else None
                    op["salida"]  = op["salida"].isoformat()  if op["salida"]  else None
                    for k in ["precio_entrada", "sl", "tp", "lotes", "pnl_virtual", "roe_pct",
                              "v_trend", "v_nlp", "v_sniper", "v_macro",
                              "v_hurst", "v_volume", "v_cross", "veredicto"]:
                        if op[k] is not None:
                            op[k] = float(op[k])
                    raw_j = op.pop("justificacion_entrada", None)
                    if raw_j:
                        try:
                            op["analisis"] = _json_lab.loads(raw_j)
                        except Exception:
                            op["analisis"] = {"ia_texto": raw_j}
                    # Bug 7: pesos_usados llega como string JSON desde la BD — parsear a dict
                    raw_p = op.get("pesos_usados")
                    if isinstance(raw_p, str):
                        try:
                            op["pesos_usados"] = _json_lab.loads(raw_p)
                        except Exception:
                            op["pesos_usados"] = {}
                    ops_recientes.append(op)
            except Exception:
                db.conn.rollback()

        # Último voto por activo del lab (desde lab_senales)
        votos_lab = []
        with db._lock:
            try:
                db.cursor.execute("""
                    SELECT DISTINCT ON (ls.activo_id)
                        a.simbolo,
                        ls.voto_tendencia, ls.voto_nlp, ls.voto_sniper, ls.voto_macro,
                        ls.voto_final_ponderado, ls.decision_gerente, ls.tiempo
                    FROM lab_senales ls
                    JOIN activos a ON a.id = ls.activo_id
                    WHERE ls.lab_id = %s
                    ORDER BY ls.activo_id, ls.tiempo DESC
                """, (lab_id,))
                for vr in db.cursor.fetchall():
                    votos_lab.append({
                        "simbolo":   vr[0],
                        "trend":     round(float(vr[1] or 0), 2),
                        "nlp":       round(float(vr[2] or 0), 2),
                        "sniper":    round(float(vr[3] or 0), 2),
                        "macro":     round(float(vr[4] or 0), 2),
                        "veredicto": round(float(vr[5] or 0), 3),
                        "decision":  vr[6],
                        "tiempo":    vr[7].isoformat() if vr[7] else None,
                    })
            except Exception:
                db.conn.rollback()

        laboratorios.append({
            "id": lab_id,
            "nombre": nombre,
            "categoria": categoria,
            "estado": estado,
            "capital_virtual": capital,
            "balance_virtual": round(balance, 2),
            "activos": activos_lab,
            "metricas": metricas,
            "operaciones_recientes": ops_recientes,
            "votos_lab": votos_lab,
            "version": version,
        })

    # Regímenes macro activos
    regimenes_macro = []
    with db._lock:
        try:
            db.cursor.execute("""
                SELECT id, tipo, nombre, fase, direccion, peso,
                       activos_afectados, razonamiento, expira_en, creado_en
                FROM regimenes_macro
                WHERE activo = TRUE
                ORDER BY peso DESC, creado_en DESC
            """)
            cols_rm = ["id", "tipo", "nombre", "fase", "direccion", "peso",
                       "activos_afectados", "razonamiento", "expira_en", "creado_en"]
            for rm_row in db.cursor.fetchall():
                rm = dict(zip(cols_rm, rm_row))
                rm["peso"] = float(rm["peso"] or 0)
                rm["expira_en"] = rm["expira_en"].isoformat() if rm["expira_en"] else None
                rm["creado_en"] = rm["creado_en"].isoformat() if rm["creado_en"] else None
                # Parsear activos_afectados si es JSON string
                if rm["activos_afectados"]:
                    try:
                        rm["activos_afectados"] = _json.loads(rm["activos_afectados"])
                    except Exception:
                        rm["activos_afectados"] = []
                else:
                    rm["activos_afectados"] = []
                regimenes_macro.append(rm)
        except Exception:
            db.conn.rollback()

    return {
        "laboratorios": laboratorios,
        "regimenes_macro": regimenes_macro,
    }


class LabEstadoUpdate(BaseModel):
    estado: str

@app.put("/api/lab/{lab_id}/estado")
async def update_lab_estado(lab_id: int, body: LabEstadoUpdate,
                             token: str = Depends(oauth2_scheme),
                             db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    estados_validos = ("ACTIVO", "INACTIVO", "GRADUADO")
    if body.estado not in estados_validos:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Opciones: {estados_validos}")
    with db._lock:
        try:
            db.cursor.execute(
                "UPDATE laboratorios SET estado = %s WHERE id = %s",
                (body.estado, lab_id)
            )
            if db.cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
            db.conn.commit()
        except HTTPException:
            raise
        except Exception as e:
            db.conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "lab_id": lab_id, "estado": body.estado}


class LabParamsUpdate(BaseModel):
    params: dict
    bump: str = "patch"   # patch | minor | major
    notas: str = ""

@app.put("/api/lab/{lab_id}/parametros")
async def update_lab_parametros(lab_id: int, body: LabParamsUpdate,
                                 token: str = Depends(oauth2_scheme),
                                 db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    if body.bump not in ("patch", "minor", "major"):
        raise HTTPException(status_code=422, detail="bump debe ser patch, minor o major")
    try:
        nueva_version = db.bump_lab_version(lab_id, body.bump, body.notas, body.params)
        return {"ok": True, "lab_id": lab_id, "version": nueva_version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lab/{lab_id}/versiones")
async def get_lab_versiones(lab_id: int,
                             token: str = Depends(oauth2_scheme),
                             db: DBConnector = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return {"versiones": db.get_lab_versiones(lab_id)}


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
        return FileResponse(
            os.path.join(_dist, "index.html"),
            headers={"Cache-Control": "no-store"}
        )
else:
    print("[PRISM] Frontend no compilado. Corre: cd dashboard/frontend && npm run build")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
