import psycopg2, json, os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('/opt/aurum/.env')

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        port=os.getenv('DB_PORT','5432'),
        dbname=os.getenv('DB_NAME','aurum_db'),
        user=os.getenv('DB_USER','aurum_admin'),
        password=os.getenv('DB_PASS','AurumProyect1milion')
    )
    c = conn.cursor(cursor_factory=RealDictCursor)

    print(":::OPERACIONES CERRADAS RECIENTES:::")
    # Using ORDER BY id DESC as a proxy for time if tiempo_cierre is missing
    query = """
    SELECT r.*, a.simbolo 
    FROM registro_operaciones r
    JOIN activos a ON r.activo_id = a.id
    WHERE r.estado IN ('CERRADA', 'PERDIDA', 'FINALIZADA')
    ORDER BY r.id DESC LIMIT 10
    """
    c.execute(query)
    rows = c.fetchall()
    if not rows:
        print("No se encontraron operaciones cerradas.")
    for o in rows:
        print(json.dumps(o, default=str))

    print(":::AUTOPSIAS DE PERDIDAS:::")
    query_autopsia = "SELECT * FROM autopsias_perdidas ORDER BY creado_en DESC LIMIT 10"
    c.execute(query_autopsia)
    autopsias = c.fetchall()
    if not autopsias:
        print("No se encontraron autopsias.")
    for a in autopsias:
        print(json.dumps(a, default=str))

    c.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
