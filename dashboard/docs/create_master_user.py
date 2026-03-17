import os
import psycopg2
import bcrypt
from dotenv import load_dotenv

def create_master_user():
    load_dotenv()
    
    # Datos del usuario maestro
    username = "msalasm"
    password = "Singluten2!"
    email = "maikol.salas.m@gmail.com"
    
    # Generar hash seguro con bcrypt
    print(f"[PRISM-AUTH] Generando hash seguro para {username}...")
    salt = bcrypt.gensalt(rounds=12)
    pwd_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
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
        
        sql = """
        INSERT INTO prism_usuarios (usuario, password_hash, rol, email, estado)
        VALUES (%s, %s, 'SUPER_ADMIN', %s, TRUE)
        ON CONFLICT (usuario) DO UPDATE
        SET password_hash = EXCLUDED.password_hash,
            email = EXCLUDED.email,
            rol = 'SUPER_ADMIN',
            estado = TRUE;
        """
        
        cursor.execute(sql, (username, pwd_hash, email))
        conn.commit()
        print(f"[PRISM-DB] SUCCESS: Usuario Maestro '{username}' creado/actualizado correctamente.")
        
        # También crear preferencias iniciales
        cursor.execute("""
            INSERT INTO prism_preferencias (usuario_id, tema_visual, efecto_velo)
            SELECT id, 'LIQUID_GOLD', TRUE FROM prism_usuarios WHERE usuario = %s
            ON CONFLICT (usuario_id) DO NOTHING;
        """, (username,))
        conn.commit()
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[PRISM-DB] ERROR: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    create_master_user()
