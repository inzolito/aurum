"""
Aurum Server Patch — 2026-03-17
Aplica 3 fixes al servidor:
  1. risk_module.py  — stops mínimos 30 pips + redondeo por dígitos
  2. risk_module.py  — deshabilitar bloqueo por drawdown (demo)
  3. MetaTrader5/__init__.py — asyncio.wait_for para timeouts correctos
"""

# ── Patch 1 & 2: risk_module.py ─────────────────────────────────────────────

path = 'core/risk_module.py'
with open(path) as f:
    txt = f.read()

changed = False

# 1a) Subir mínimo de stops a 30 pips
old_stops = (
    '        min_dist = max(info.spread, info.trade_stops_level) * info.point\n'
    '        min_sl = min_dist * 1.5\n'
    '        min_tp = min_dist * 2.0'
)
new_stops = (
    '        pip = info.point * 10\n'
    '        min_dist = max(max(info.spread, info.trade_stops_level) * info.point, pip * 30)\n'
    '        min_sl = min_dist * 1.5\n'
    '        min_tp = min_dist * 2.0'
)
if old_stops in txt:
    txt = txt.replace(old_stops, new_stops)
    print("OK: stops mínimos → 30 pips")
    changed = True
else:
    print("SKIP: patrón stops no encontrado (¿ya aplicado?)")

# 1b) Redondeo por dígitos antes del return
old_return = '        return sl, tp'
new_return = (
    '        digits = info.digits\n'
    '        return round(sl, digits), round(tp, digits)'
)
if old_return in txt and 'round(sl,' not in txt:
    txt = txt.replace(old_return, new_return)
    print("OK: redondeo por dígitos agregado")
    changed = True
else:
    print("SKIP: redondeo ya presente o patrón no encontrado")

# 1c) Deshabilitar bloqueo por drawdown
old_draw = (
    '        acc_info = mt5_lib.account_info()\n'
    '        if acc_info:\n'
    '            if acc_info.profit < -max_perdida_flotante:\n'
    '                print(f"[RISK] BLOQUEO DE SEGURIDAD: Pérdida flotante ({acc_info.profit:.2f} USD) supera el umbral de ${max_perdida_flotante:.0f}.")\n'
    '                return False'
)
new_draw = (
    '        # DRAWDOWN CHECK DESHABILITADO (demo)\n'
    '        # acc_info = mt5_lib.account_info()\n'
    '        # if acc_info and acc_info.profit < -max_perdida_flotante:\n'
    '        #     return False'
)
if old_draw in txt:
    txt = txt.replace(old_draw, new_draw)
    print("OK: bloqueo drawdown deshabilitado")
    changed = True
else:
    print("SKIP: patrón drawdown no encontrado (¿ya comentado?)")

if changed:
    with open(path, 'w') as f:
        f.write(txt)
    print(f"  → {path} guardado")


# ── Patch 3: MetaTrader5/__init__.py ────────────────────────────────────────

path2 = 'MetaTrader5/__init__.py'
with open(path2) as f:
    txt2 = f.read()

changed2 = False

old_run = (
    'def _run(coro, timeout=30):\n'
    '    """Ejecuta una coroutine async de forma síncrona."""\n'
    '    future = asyncio.run_coroutine_threadsafe(coro, _loop)\n'
    '    try:\n'
    '        return future.result(timeout=timeout)\n'
    '    except (concurrent.futures.TimeoutError, asyncio.TimeoutError):\n'
    '        future.cancel()\n'
    '        _set_last_error(1, "MetaAPI timeout")\n'
    '        return None\n'
    '    except Exception as e:\n'
    '        future.cancel()\n'
    '        _set_last_error(1, str(e))\n'
    '        return None'
)
new_run = (
    'def _run(coro, timeout=30):\n'
    '    """Ejecuta una coroutine async de forma síncrona."""\n'
    '    async def _with_timeout():\n'
    '        return await asyncio.wait_for(coro, timeout=timeout - 2)\n'
    '\n'
    '    future = asyncio.run_coroutine_threadsafe(_with_timeout(), _loop)\n'
    '    try:\n'
    '        return future.result(timeout=timeout)\n'
    '    except (concurrent.futures.TimeoutError, asyncio.TimeoutError):\n'
    '        future.cancel()\n'
    '        _set_last_error(1, "MetaAPI timeout")\n'
    '        return None\n'
    '    except Exception as e:\n'
    '        future.cancel()\n'
    '        detail = getattr(e, "details", None)\n'
    '        msg = str(e) + " | details: " + str(detail) if detail else str(e)\n'
    '        _set_last_error(1, msg)\n'
    '        return None'
)

if 'wait_for' in txt2:
    print("SKIP: asyncio.wait_for ya presente en el shim")
elif old_run in txt2:
    txt2 = txt2.replace(old_run, new_run)
    print("OK: asyncio.wait_for agregado al shim")
    changed2 = True
else:
    print("WARN: patrón _run no encontrado — mostrando líneas relevantes:")
    for i, line in enumerate(txt2.splitlines(), 1):
        if 'def _run' in line or 'future' in line or 'timeout' in line:
            print(f"  {i}: {line}")

if changed2:
    with open(path2, 'w') as f:
        f.write(txt2)
    print(f"  → {path2} guardado")

print("\nListo. Reiniciar con: sudo systemctl restart aurum-core")
