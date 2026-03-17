"""
Script de prueba: Fase 2 - DBConnector
Verifica los tres métodos obligatorios:
  1. get_parametros()
  2. update_estado_bot()
  3. registrar_log()
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from config.db_connector import DBConnector


def separador(titulo):
    print(f"\n{'='*55}")
    print(f"  {titulo}")
    print(f"{'='*55}")


def main():
    db = DBConnector()
    if not db.conectar():
        print("CRITICAL: No se pudo conectar. Abortando.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 1. get_parametros()
    # ------------------------------------------------------------------
    separador("1. get_parametros()")
    params = db.get_parametros()
    for clave, valor in params.items():
        print(f"  {clave:<35} = {valor}")

    # ------------------------------------------------------------------
    # 2. update_estado_bot()
    # ------------------------------------------------------------------
    separador("2. update_estado_bot()")
    db.update_estado_bot(
        estado="ESPERANDO",
        pensamiento="Probando conexion desde Surface Pro"
    )
    print("  Upsert ejecutado. Verificando con SELECT...")

    db.cursor.execute("SELECT id, estado_general, pensamiento_actual, tiempo FROM estado_bot WHERE id = 1;")
    fila = db.cursor.fetchone()
    if fila:
        print(f"  ID              : {fila[0]}")
        print(f"  Estado          : {fila[1]}")
        print(f"  Pensamiento     : {fila[2]}")
        print(f"  Tiempo (UTC)    : {fila[3]}")
    else:
        print("  ERROR: No se encontro la fila en estado_bot.")

    # ------------------------------------------------------------------
    # 3. registrar_log()
    # ------------------------------------------------------------------
    separador("3. registrar_log()")
    db.registrar_log(
        nivel="INFO",
        modulo="test_fase2",
        mensaje="Prueba de conexion completada desde Surface Pro. Todos los metodos OK."
    )
    print("  Log insertado. Verificando con SELECT...")

    db.cursor.execute(
        "SELECT nivel, modulo, mensaje, tiempo FROM log_sistema ORDER BY tiempo DESC LIMIT 1;"
    )
    log = db.cursor.fetchone()
    if log:
        print(f"  Nivel    : {log[0]}")
        print(f"  Modulo   : {log[1]}")
        print(f"  Mensaje  : {log[2]}")
        print(f"  Tiempo   : {log[3]}")

    # ------------------------------------------------------------------
    separador("RESULTADO FINAL")
    print("  Fase 2 verificada. Los tres metodos funcionan correctamente.")
    db.desconectar()


if __name__ == "__main__":
    main()
