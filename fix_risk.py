# -*- coding: utf-8 -*-
with open('/opt/aurum/core/risk_module.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    stripped = line.strip()
    # Detectar el return False huerfano (tiene indentacion de 16 espacios = dentro de if anidado)
    if stripped == 'return False' and line.startswith('                return False'):
        # Verificar que el contexto sean lineas comentadas (drawdown)
        context = ''.join(new_lines[-6:])
        if 'DRAWDOWN' in context or 'acc_info' in context:
            new_lines.append('        # return False  # DRAWDOWN DESHABILITADO\n')
            continue
    new_lines.append(line)

with open('/opt/aurum/core/risk_module.py', 'w') as f:
    f.writelines(new_lines)

import py_compile
py_compile.compile('/opt/aurum/core/risk_module.py', doraise=True)
print('OK - sintaxis correcta')
