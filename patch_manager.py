# -*- coding: utf-8 -*-
with open("/opt/aurum/core/manager.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: rollback antes del loop para limpiar transaccion abortada
old1 = '''        for ticket, veredicto, prob, p_ent, tp, sl, simbolo in pendientes:'''
new1 = '''        try:
            self.db.conn.rollback()
        except Exception:
            pass

        for ticket, veredicto, prob, p_ent, tp, sl, simbolo in pendientes:'''

# Fix 2: rollback en el except del UPDATE
old2 = '''                except Exception as e:
                    print(f"[GERENTE] Error actualizando precision de cierre #{ticket}: {e}")'''
new2 = '''                except Exception as e:
                    print(f"[GERENTE] Error actualizando precision de cierre #{ticket}: {e}")
                    try:
                        self.db.conn.rollback()
                    except Exception:
                        pass'''

# Fix 3: float(veredicto) -> float(veredicto or 0) en ambas notificaciones
old3 = "veredicto=float(veredicto),"
new3 = "veredicto=float(veredicto or 0),"

count = 0
for old, new in [(old1, new1), (old2, new2)]:
    if old in content:
        content = content.replace(old, new, 1)
        count += 1
    else:
        print(f"WARN: no encontrado: {old[:60]!r}")

content = content.replace(old3, new3)

with open("/opt/aurum/core/manager.py", "w", encoding="utf-8") as f:
    f.write(content)

print(f"OK - {count} bloques reemplazados + float(veredicto or 0)")
