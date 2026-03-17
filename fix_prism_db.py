import os
import psycopg2
import bcrypt
from dotenv import load_dotenv

def fix_prism():
    load_dotenv()
    
    # Intentar primero con la config del bot, luego con localhost
    hosts = [os.getenv("DB_HOST"), "localhost", "127.0.0.1"]
    conn = None
    
    for host in hosts:
        if not host: continue
        try:
            print(f"[FIX] Probando conexión en {host}...")
            conn = psycopg2.connect(
                host=host,
                port=os.getenv("DB_PORT", 5432),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                connect_timeout=3
            )
            print(f"[FIX] ¡Conexión exitosa en {host}!")
            break
        except Exception as e:
            print(f"[FIX] Falló conexión en {host}: {e}")
            
    if not conn:
        print("[ERROR] No se pudo conectar a la DB por ninguna vía.")
        return

    try:
        cur = conn.cursor()
        
        # 1. Crear Tablas
        print("[FIX] Creando tablas prism_...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS prism_usuarios (
            id SERIAL PRIMARY KEY,
            usuario VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol VARCHAR(20) DEFAULT 'SUPER_ADMIN',
            estado BOOLEAN DEFAULT TRUE
        );
        CREATE TABLE IF NOT EXISTS prism_log_seguridad (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER,
            evento VARCHAR(50),
            ip_origen VARCHAR(45),
            fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS prism_sesiones (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER,
            token_jwt TEXT,
            creado_en TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. Crear Usuario Maestro
        print("[FIX] Creando/Actualizando usuario msalasm...")
        pwd_hash = bcrypt.hashpw("Singluten2!".encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        cur.execute("""
            INSERT INTO prism_usuarios (usuario, password_hash, rol, estado)
            VALUES ('msalasm', %s, 'SUPER_ADMIN', TRUE)
            ON CONFLICT (usuario) DO UPDATE SET password_hash = EXCLUDED.password_hash;
        """, (pwd_hash,))
        
        conn.commit()
        print("[SUCCESS] Sistema Prism configurado y listo para login.")
        
    except Exception as e:
        print(f"[ERROR] Error durante la migración: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    fix_prism()
