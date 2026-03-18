import sys
import os
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
        except Exception:
            db.conn.rollback()

        try:
            db.cursor.execute("SELECT COUNT(*) FROM registro_operaciones WHERE cerrado_en IS NULL")
            result["posiciones_abiertas"] = db.cursor.fetchone()[0] or 0
        except Exception:
            db.conn.rollback()

        try:
            db.cursor.execute(
                "SELECT COUNT(*), COALESCE(SUM(pnl_usd), 0) FROM registro_operaciones WHERE DATE(tiempo_apertura) = CURRENT_DATE"
            )
            row = db.cursor.fetchone()
            if row:
                result["trades_hoy"] = row[0] or 0
                result["pnl_hoy"] = float(row[1] or 0)
        except Exception:
            db.conn.rollback()

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
                       ro.tamano_real_usd, ro.tiempo_apertura
                FROM registro_operaciones ro
                JOIN activos a ON a.id = ro.activo_id
                WHERE ro.cerrado_en IS NULL
                ORDER BY ro.tiempo_apertura DESC
            """)
            cols = ["simbolo", "ticket", "tipo", "lotes", "precio_entrada", "sl", "tp", "tamano_usd", "apertura"]
            rows = db.cursor.fetchall()
            posiciones = []
            for r in rows:
                d = dict(zip(cols, r))
                if d.get("apertura"):
                    d["apertura"] = d["apertura"].isoformat()
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
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            rows = db.cursor.fetchall()
            noticias = []
            for r in rows:
                title, source, summary, ts, pub_at = r
                impacto = None
                tipo = "filtrada"
                if summary and "Impacto:" in summary:
                    try:
                        impacto = int(summary.split("|")[0].replace("Impacto:", "").strip())
                        tipo = "relevante"
                    except Exception:
                        pass
                elif summary and "Descargada" in summary:
                    tipo = "descartada"
                noticias.append({
                    "titulo": title,
                    "fuente": source,
                    "impacto": impacto,
                    "tipo": tipo,
                    "timestamp": ts.isoformat() if ts else None,
                    "published_at": pub_at.isoformat() if pub_at else None,
                })
            return {"noticias": noticias, "total": len(noticias)}
        except Exception:
            db.conn.rollback()
            return {"noticias": [], "total": 0}


@app.get("/health")
async def health_check():
    return {"status": "operational", "version": "Prism 1.0"}


# ── Servir frontend compilado (SPA) ──────────────────────────────────────────
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(_dist):
    _assets = os.path.join(_dist, "assets")
    if os.path.exists(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}")
    async def spa_handler(full_path: str):
        return FileResponse(os.path.join(_dist, "index.html"))
else:
    print("[PRISM] Frontend no compilado. Corre: cd dashboard/frontend && npm run build")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
