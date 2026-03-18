#!/usr/bin/env python3
"""
sync_operaciones.py — Importa posiciones abiertas y deals históricos de MT5/MetaAPI → PostgreSQL.
Uso: python scripts/sync_operaciones.py [--dias 90]
"""
import sys, os, asyncio, argparse
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))

from datetime import datetime, timezone, timedelta
from config.db_connector import DBConnector

# ─── Config ───────────────────────────────────────────────────────────────────
TOKEN      = os.getenv('METAAPI_TOKEN', '')
ACCOUNT_ID = os.getenv('METAAPI_ACCOUNT_ID', '')

def _g(obj, *keys, default=None):
    """Obtiene un campo de un dict o de un objeto con atributos."""
    for key in keys:
        val = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
        if val is not None:
            return val
    return default

def _ts(val):
    """Convierte string ISO / datetime a datetime tz-aware."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        return datetime.fromisoformat(val.replace('Z', '+00:00'))
    return None

# ─── DB helpers ───────────────────────────────────────────────────────────────
def db_connect():
    db = DBConnector()
    if not db.conectar():
        os.environ['DB_HOST'] = 'localhost'
        if not db.conectar():
            raise Exception("No se pudo conectar a la base de datos")
    return db

def get_activos(db):
    with db._lock:
        db.cursor.execute("SELECT simbolo, id FROM activos")
        return {r[0]: r[1] for r in db.cursor.fetchall()}

def match_symbol(symbol, activos_map):
    """Busca activo_id para un símbolo, tolerando sufijos de broker (e.g. XAUUSDm)."""
    if symbol in activos_map:
        return activos_map[symbol]
    # Eliminar sufijos comunes
    for suffix in ('m', '.r', '+', '#', '_'):
        candidate = symbol.rstrip(suffix)
        if candidate in activos_map:
            return activos_map[candidate]
    # Prefijo parcial
    for s, aid in activos_map.items():
        if symbol.startswith(s) or s.startswith(symbol[:6]):
            return aid
    return None

def ticket_exists(db, ticket):
    with db._lock:
        db.cursor.execute("SELECT 1 FROM registro_operaciones WHERE ticket_mt5 = %s", (ticket,))
        return db.cursor.fetchone() is not None

def to_ticket(raw):
    try:
        return int(raw)
    except (ValueError, TypeError):
        return abs(hash(str(raw))) % 10**9

# ─── MetaAPI ──────────────────────────────────────────────────────────────────
async def fetch_metaapi(dias):
    from metaapi_cloud_sdk import MetaApi

    print(f"[SYNC] Conectando a MetaAPI (account={ACCOUNT_ID[:8]}...)...")
    api     = MetaApi(TOKEN)
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)

    # Usar RPC igual que el shim (patrón probado)
    conn = account.get_rpc_connection()
    await conn.connect()
    print("[SYNC] Esperando sincronización...")
    await asyncio.wait_for(conn.wait_synchronized(), timeout=90)

    ws = conn._websocket_client
    account_id = account.id

    # 1. Posiciones abiertas
    try:
        raw_pos = await ws.get_positions(account_id)
        open_pos = list(raw_pos or [])
    except Exception as e:
        print(f"[SYNC] Error obteniendo posiciones: {e}")
        open_pos = []
    print(f"[SYNC] Posiciones abiertas: {len(open_pos)}")

    # 2. Deals históricos
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=dias)
    deals = []
    try:
        raw_deals = await ws.get_deals_by_time_range(account_id, start, end)
        deals = list(raw_deals or [])
    except Exception as e:
        print(f"[SYNC] get_deals_by_time_range: {e}")

    print(f"[SYNC] Deals históricos encontrados: {len(deals)}")

    try:
        await conn.close()
    except Exception:
        pass
    try:
        api.close()
    except Exception:
        pass

    return open_pos, deals

# ─── Procesamiento ────────────────────────────────────────────────────────────
def process_open(db, activos, open_pos):
    count = 0
    for p in open_pos:
        symbol = _g(p, 'symbol')
        ticket = to_ticket(_g(p, 'id'))

        if ticket_exists(db, ticket):
            continue

        activo_id = match_symbol(symbol, activos)
        if not activo_id:
            print(f"[SYNC] Sin activo para '{symbol}', omitiendo.")
            continue

        ptype = _g(p, 'type', 'positionType', default='')
        tipo  = 'COMP' if 'BUY' in str(ptype).upper() else 'VENT'

        with db._lock:
            db.cursor.execute("""
                INSERT INTO registro_operaciones
                    (activo_id, ticket_mt5, tipo_orden, volumen_lotes,
                     precio_entrada, stop_loss, take_profit, tiempo_entrada)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                activo_id, ticket, tipo,
                float(_g(p, 'volume', default=0) or 0),
                float(_g(p, 'openPrice', 'price', default=0) or 0),
                float(_g(p, 'stopLoss', 'sl', default=0) or 0),
                float(_g(p, 'takeProfit', 'tp', default=0) or 0),
                _ts(_g(p, 'time', 'openTime')),
            ))
        count += 1
        print(f"  [+] Abierta: {symbol} {tipo} ticket={ticket}")
    return count

def process_deals(db, activos, deals):
    ins, outs = {}, {}
    for d in deals:
        entry = str(_g(d, 'entryType', 'entry', default='')).upper()
        pid   = str(_g(d, 'positionId', default=''))
        if 'IN' in entry or entry == '0':
            ins[pid] = d
        elif 'OUT' in entry or entry == '1':
            outs[pid] = d

    count = 0
    for pid, d_in in ins.items():
        symbol = _g(d_in, 'symbol', default='')
        ticket = to_ticket(_g(d_in, 'id', default=pid))

        if ticket_exists(db, ticket):
            continue

        activo_id = match_symbol(symbol, activos)
        if not activo_id:
            continue

        dtype = str(_g(d_in, 'type', default='')).upper()
        tipo  = 'COMP' if 'BUY' in dtype else 'VENT'
        t_in  = _ts(_g(d_in, 'time'))

        d_out     = outs.get(pid)
        pnl       = float(_g(d_out, 'profit', default=0) or 0) if d_out else None
        resultado = ('WIN' if pnl >= 0 else 'LOSS') if d_out else None

        with db._lock:
            db.cursor.execute("""
                INSERT INTO registro_operaciones
                    (activo_id, ticket_mt5, tipo_orden, volumen_lotes,
                     precio_entrada, tiempo_entrada, pnl_usd, resultado_final)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                activo_id, ticket, tipo,
                float(_g(d_in, 'volume', default=0) or 0),
                float(_g(d_in, 'price', default=0) or 0),
                t_in, pnl, resultado,
            ))
        count += 1

    return count

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dias', type=int, default=90,
                        help='Días de historial a importar (default: 90)')
    args = parser.parse_args()

    if not TOKEN or not ACCOUNT_ID:
        print("[SYNC] ERROR: METAAPI_TOKEN o METAAPI_ACCOUNT_ID no configurados en .env")
        sys.exit(1)

    open_pos, deals = asyncio.run(fetch_metaapi(args.dias))

    db = db_connect()
    activos = get_activos(db)
    print(f"[SYNC] Activos en BD: {list(activos.keys())}")

    n_open   = process_open(db, activos, open_pos)
    n_closed = process_deals(db, activos, deals)
    with db._lock:
        db.conn.commit()
    db.desconectar()

    print(f"\n[SYNC] ✓ Importadas: {n_open} abiertas + {n_closed} cerradas")

if __name__ == '__main__':
    main()
