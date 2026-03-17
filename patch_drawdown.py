"""
Fix: deshabilitar kill-switch de drawdown en risk_module.py y main.py
"""

# ── risk_module.py ───────────────────────────────────────────────────────────
path = 'core/risk_module.py'
with open(path) as f:
    lines = f.readlines()

new_lines = []
skip_next = 0
for line in lines:
    if skip_next > 0:
        new_lines.append('        # ' + line.lstrip())
        skip_next -= 1
        continue
    if 'acc_info.profit' in line and 'max_perdida_flotante' in line:
        new_lines.append('        # DRAWDOWN DESHABILITADO\n')
        new_lines.append('        # ' + line.lstrip())
        continue
    if 'acc_info = mt5_lib.account_info()' in line:
        new_lines.append('        # ' + line.lstrip())
        skip_next = 1
        continue
    if 'BLOQUEO DE SEGURIDAD' in line and 'flotante' in line:
        new_lines.append('        # ' + line.lstrip())
        continue
    new_lines.append(line)

with open(path, 'w') as f:
    f.writelines(new_lines)
print("risk_module.py OK")


# ── main.py ──────────────────────────────────────────────────────────────────
# Estrategia: reemplazar el bloque entero por un pass comentado
path2 = 'main.py'
with open(path2) as f:
    txt = f.read()

# Buscar y comentar el bloque completo del kill-switch en main.py
# El bloque va desde "_params_dd = self.db.get_parametros()" hasta "break"
import re

pattern = re.compile(
    r'( +)(_params_dd = self\.db\.get_parametros\(\)\n'
    r'\s+_max_dd = .*?\n'
    r'\s+if info_acc and info_acc\.equity < _max_dd:.*?\n'
    r'(?:\s+.*?\n)*?'
    r'\s+break\n)',
    re.MULTILINE
)

def comentar_bloque(m):
    indent = m.group(1)
    bloque = m.group(0)
    lineas = bloque.splitlines(keepends=True)
    comentadas = [indent + '# ' + l.lstrip() for l in lineas]
    return ''.join(comentadas)

nuevo_txt, n = re.subn(pattern, comentar_bloque, txt)

if n > 0:
    with open(path2, 'w') as f:
        f.write(nuevo_txt)
    print(f"main.py OK ({n} bloque(s) comentado(s))")
else:
    # Fallback: buscar línea a línea y comentar todo lo que sigue al if hasta break
    print("Regex no matcheó, aplicando fallback línea a línea...")
    lines2 = txt.splitlines(keepends=True)
    new_lines2 = []
    inside_block = False
    for line in lines2:
        if 'info_acc and info_acc.equity < _max_dd' in line:
            inside_block = True
            new_lines2.append('                # KILL-SWITCH DESHABILITADO (demo)\n')
            new_lines2.append('                # ' + line.lstrip())
            continue
        if inside_block:
            new_lines2.append('                # ' + line.lstrip())
            if 'break' in line:
                inside_block = False
            continue
        new_lines2.append(line)
    with open(path2, 'w') as f:
        f.writelines(new_lines2)
    print("main.py OK (fallback)")


# ── Verificar sintaxis ───────────────────────────────────────────────────────
import py_compile, sys
for f in ['core/risk_module.py', 'main.py']:
    try:
        py_compile.compile(f, doraise=True)
        print(f"Sintaxis OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"ERROR sintaxis en {f}: {e}")
        sys.exit(1)

print("\nListo. Correr: sudo systemctl restart aurum-core")
