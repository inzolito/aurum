import os
import psycopg2
from dotenv import load_dotenv
import traceback

def apply_prism_migration():
    load_dotenv()
    
    conn = None
    try:
        print("[PRISM-DB] Conectando a la base de datos...")
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT", 5432),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            connect_timeout=10
        )
        cursor = conn.cursor()
        
        # Intentamos habilitar pgcrypto para gen_random_uuid()
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        except:
            conn.rollback() # Ignoramos si no tenemos permisos
            print("[PRISM-DB] No se pudo activar pgcrypto, se usara esquema alternativo para IDs.")

        sql_script = """
        -- Aurum Prism Database Schema - Level 0

        -- 🔐 1. Tabla: prism_usuarios
        CREATE TABLE IF NOT EXISTS prism_usuarios (
            id SERIAL PRIMARY KEY,
            usuario VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email VARCHAR(100),
            rol VARCHAR(20) DEFAULT 'AUDITOR',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_acceso TIMESTAMP,
            estado BOOLEAN DEFAULT TRUE
        );

        -- 🎟️ 2. Tabla: prism_sesiones
        CREATE TABLE IF NOT EXISTS prism_sesiones (
            id VARCHAR(64) PRIMARY KEY,
            usuario_id INTEGER REFERENCES prism_usuarios(id) ON DELETE CASCADE,
            token TEXT,
            ip_origen VARCHAR(45),
            user_agent TEXT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expira_en TIMESTAMP
        );

        -- 🎨 3. Tabla: prism_preferencias
        CREATE TABLE IF NOT EXISTS prism_preferencias (
            usuario_id INTEGER PRIMARY KEY REFERENCES prism_usuarios(id) ON DELETE CASCADE,
            tema_visual VARCHAR(20) DEFAULT 'LIGHT_GOLD',
            efecto_velo BOOLEAN DEFAULT TRUE,
            densidad_particulas FLOAT DEFAULT 1.0,
            activos_favoritos TEXT[]
        );

        -- 🚨 4. Tabla: prism_log_seguridad
        CREATE TABLE IF NOT EXISTS prism_log_seguridad (
            id SERIAL PRIMARY KEY,
            usuario_intento VARCHAR(50),
            evento VARCHAR(50),
            ip_origen VARCHAR(45),
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Insertar usuario inicial (Maikol) - Password temporal: 'prism2026' (hash bcrypt)
        INSERT INTO prism_usuarios (usuario, password_hash, rol, email)
        VALUES ('maikol', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6L6S8d1S3D.i1.mK', 'SUPER_ADMIN', 'maikol@aurum.prism')
        ON CONFLICT (usuario) DO NOTHING;
        """
        
        print("[PRISM-DB] Ejecutando script de migracion...")
        cursor.execute(sql_script)
        conn.commit()
        print("[PRISM-DB] SUCCESS: Migracion completada con exito. Tablas prism_ creadas.")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print("[PRISM-DB] ERROR en la migracion:")
        print(str(e))
        traceback.print_exc()
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    apply_prism_migration()
