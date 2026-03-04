import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Añadir el root del proyecto al path para importar db_connector
sys.path.append(str(Path(__file__).parent.parent))
from config.db_connector import DBConnector

load_dotenv()

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _split_statements(sql: str) -> list:
    """Divide el SQL en sentencias individuales ignorando los comentarios inline."""
    statements = []
    current = []
    for line in sql.splitlines():
        clean = line.split("--")[0].rstrip()
        current.append(clean)
        if clean.rstrip().endswith(";"):
            stmt = "\n".join(current).strip().rstrip(";")
            if stmt:
                statements.append(stmt)
            current = []
    return statements


def run_migration(db: DBConnector, archivo: Path):
    print(f"\n[MIG] Ejecutando: {archivo.name}")
    sql = archivo.read_text(encoding="utf-8")

    statements = _split_statements(sql)
    ok = 0
    skip = 0
    for stmt in statements:
        try:
            db.cursor.execute(stmt)
            db.conn.commit()
            ok += 1
        except Exception as e:
            db.conn.rollback()
            err = str(e).split("\n")[0]
            print(f"[MIG] SKIP -> {err}")
            skip += 1

    print(f"[MIG] OK -> {archivo.name}: {ok} sentencias aplicadas, {skip} omitidas (ya existian).")


def verificar_activos(db: DBConnector):
    print("\n[VER] SELECT * FROM activos;")
    db.cursor.execute("SELECT id, simbolo, nombre, categoria, estado_operativo FROM activos;")
    filas = db.cursor.fetchall()
    if not filas:
        print("[VER] La tabla activos esta vacia.")
    else:
        print(f"{'ID':<5} {'SIMBOLO':<10} {'NOMBRE':<25} {'CATEGORIA':<12} {'ESTADO'}")
        print("-" * 65)
        for fila in filas:
            print(f"{fila[0]:<5} {fila[1]:<10} {fila[2]:<25} {fila[3]:<12} {fila[4]}")


def main():
    db = DBConnector()
    if not db.conectar():
        print("[MIG] CRITICAL: No se pudo conectar a la base de datos. Abortando.")
        sys.exit(1)

    archivos = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not archivos:
        print("[MIG] No se encontraron archivos .sql en database/migrations/")
        db.desconectar()
        return

    print(f"[MIG] {len(archivos)} migracion(es) encontrada(s):")
    for f in archivos:
        print(f"      - {f.name}")

    for archivo in archivos:
        run_migration(db, archivo)

    verificar_activos(db)
    db.desconectar()
    print("\n[MIG] Proceso completado.")


if __name__ == "__main__":
    main()
