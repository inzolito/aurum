"""
Script de diagnóstico y migración para FIX-NLP-02, FIX-VOL-02, FIX-CROSS-02
Ejecutar: pythonw.exe run_v15fixes.py  o  python run_v15fixes.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config.db_connector import DBConnector

db = DBConnector()
if not db.conectar():
    print('ERROR: No se pudo conectar a la BD')
    sys.exit(1)

print('=' * 60)
print('AURUM V15 — Diagnóstico y Migración de Workers')
print('=' * 60)

# 1. Limpiar caché NLP duplicado
print('\n[1] FIX-NLP-02: Limpiando cache_nlp_impactos duplicados...')
try:
    db.cursor.execute('''
        DELETE FROM cache_nlp_impactos
        WHERE id NOT IN (
            SELECT DISTINCT ON (simbolo) id
            FROM cache_nlp_impactos
            ORDER BY simbolo, creado_en DESC
        )
    ''')
    deleted = db.cursor.rowcount
    db.conn.commit()
    print(f'   Filas duplicadas eliminadas: {deleted}')
except Exception as e:
    print(f'   Error limpiando duplicados: {e}')
    db.conn.rollback()

# 2. Crear UNIQUE constraint
print('\n[2] Verificando UNIQUE constraint en cache_nlp_impactos...')
try:
    db.cursor.execute('''
        SELECT constraint_name FROM information_schema.table_constraints 
        WHERE table_name = %s AND constraint_name = %s
    ''', ('cache_nlp_impactos', 'cache_nlp_impactos_simbolo_key'))
    existe = db.cursor.fetchone()
    if not existe:
        db.cursor.execute('ALTER TABLE cache_nlp_impactos ADD CONSTRAINT cache_nlp_impactos_simbolo_key UNIQUE (simbolo)')
        db.conn.commit()
        print('   UNIQUE constraint creado exitosamente ✓')
    else:
        print('   UNIQUE constraint ya existía ✓')
except Exception as e:
    print(f'   Error con constraint: {e}')
    try:
        db.conn.rollback()
    except:
        pass

# 3. Test sensores CrossWorker
print('\n[3] FIX-CROSS-02: Verificando sensores en MT5...')
try:
    import MetaTrader5 as mt5
    if mt5.initialize():
        sensores = ['SPXUSD', 'SPXUSD_i', 'EURUSD_i', 'XTIUSD_i']
        for sym in sensores:
            mt5.symbol_select(sym, True)
            tick = mt5.symbol_info_tick(sym)
            status = f'OK bid={tick.bid:.4f}' if tick else 'SIN DATOS'
            print(f'   {sym:15s}: {status}')
        mt5.shutdown()
        print()
        print('   → Si SPXUSD no tiene datos pero SPXUSD_i sí, el fix es correcto.')
        print('   → Si ninguno tiene datos, el CrossWorker retornará 0 (comportamiento esperado).')
    else:
        print('   MT5 no disponible (normal si el bot no está corriendo)')
except Exception as e:
    print(f'   MT5 test error: {e}')

# 4. Estado del caché NLP post-migración
print('\n[4] Estado del caché NLP (últimas 15 entradas):')
try:
    db.cursor.execute('''
        SELECT simbolo, voto, creado_en 
        FROM cache_nlp_impactos 
        ORDER BY creado_en DESC LIMIT 15
    ''')
    rows = db.cursor.fetchall()
    if rows:
        for r in rows:
            age_min = (r[2].replace(tzinfo=None) - r[2].replace(tzinfo=None)).seconds // 60 if r[2] else 0
            print(f'   {r[0]:10s} voto={r[1]:+.2f}  ts={r[2]}')
    else:
        print('   Caché vacío → se llenará en el próximo ciclo del bot ✓')
except Exception as e:
    print(f'   Error leyendo caché: {e}')

# 5. Verificar tabla VolumeWorker (no necesita migración)
print('\n[5] FIX-VOL-02: ')
print('   Sin migración de BD requerida.')
print('   El fix es en worker_volume.py: usa (bid+ask)/2 en lugar de .last en Forex.')

db.desconectar()
print()
print('=' * 60)
print('Migración completada. Reiniciar el bot para aplicar los fixes.')
print('=' * 60)
