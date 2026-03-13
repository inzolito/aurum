"""
Runner de migraciones SQL para Aurum.
Uso: python db/apply_migration.py db/migration_v15_broker_map.sql
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from config.db_connector import DBConnector

if len(sys.argv) < 2:
    print("Uso: python db/apply_migration.py <archivo.sql>")
    sys.exit(1)

sql_file = sys.argv[1]
if not os.path.exists(sql_file):
    print(f"Archivo no encontrado: {sql_file}")
    sys.exit(1)

with open(sql_file, 'r', encoding='utf-8') as f:
    sql = f.read()

db = DBConnector()
if not db.conectar():
    print("ERROR: No se pudo conectar a la base de datos.")
    sys.exit(1)

# Ejecutar sentencia por sentencia (ignorando comentarios y líneas vacías)
def _clean_stmt(s):
    """Elimina líneas de comentario y devuelve el SQL limpio."""
    lines = [l for l in s.splitlines() if l.strip() and not l.strip().startswith('--')]
    return '\n'.join(lines).strip()

statements = [_clean_stmt(s) for s in sql.split(';') if _clean_stmt(s)]
for stmt in statements:
    try:
        db.cursor.execute(stmt)
        if stmt.upper().startswith('SELECT'):
            rows = db.cursor.fetchall()
            cols = [d[0] for d in db.cursor.description]
            print('\t'.join(cols))
            print('-' * 60)
            for row in rows:
                print('\t'.join(str(v) for v in row))
        else:
            print(f"OK ({db.cursor.rowcount} filas afectadas): {stmt[:60]}...")
    except Exception as e:
        db.conn.rollback()
        print(f"ERROR en: {stmt[:80]}\n  → {e}")
        sys.exit(1)

db.conn.commit()
print("\nMigración aplicada correctamente.")
db.desconectar()
