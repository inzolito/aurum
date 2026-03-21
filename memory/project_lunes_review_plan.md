---
name: Plan de Revisión Lunes — V18.1 Primera Apertura
description: Checklist ordenado para verificar que MacroWorker, Lab Cripto y todos los cambios V18/V18.1 funcionan correctamente en el primer ciclo real del lunes.
type: project
---

## Contexto

El lunes es la primera vez que el bot corre con:
- **MacroWorker** activo en el ensemble de producción (voto_macro en registro_senales)
- **Lab Cripto** en estado ACTIVO evaluando BTCUSD y ETHUSD
- **BTCUSD/ETHUSD** como activos nuevos (simbolo_broker seteado, nunca evaluados antes)
- **LabEvaluator** corriendo al final de cada ciclo
- **voto_macro** en lab_senales y registro_senales

Mercado abre: **Domingo 22:00 UTC (domingo noche, lunes madrugada Chile)**

---

## Paso 0 — Antes de abrir (Domingo 21:45 UTC)

Verificar que todo sigue en pie después del fin de semana.

```bash
# Bot corriendo sin errores
journalctl -u aurum-core --no-pager -n 20

# Dashboard respondiendo
curl -s http://localhost:8000/api/health | head -20

# Lab Cripto sigue ACTIVO
sudo -u postgres psql -d aurum_db -c \
  "SELECT id, nombre, estado, balance_virtual FROM laboratorios WHERE id=7;"
```

**Esperado:** aurum-core activo, dashboard responde, Lab Cripto = ACTIVO

---

## Paso 1 — Primer ciclo (primeros 3 minutos tras apertura)

El bot sale de VIGILANCIA y corre el primer ciclo completo con todos los activos.

```bash
# Ver logs en tiempo real
journalctl -u aurum-core -f
```

**Buscar en logs:**
- `[GERENTE] 🌐 MacroWorker:` → confirma que el worker votó en producción
- `[LAB] Ciclo evaluacion:` → confirma que LabEvaluator corrió
- `[LAB] Lab 7 | BTCUSD` o `[LAB] Lab 7 | ETHUSD` → activos cripto evaluados
- **AUSENCIA de:**
  - `ERROR` o `Traceback` relacionados con voto_macro o lab_evaluator
  - `[GERENTE] FALLO CRITICO` en BTCUSD o ETHUSD

---

## Paso 2 — Verificar MacroWorker en producción (después del primer ciclo)

```sql
-- Verificar que voto_macro se guardó (no todas 0)
SELECT
    a.simbolo,
    rs.decision_gerente,
    rs.voto_tendencia,
    rs.voto_nlp,
    rs.voto_macro,
    rs.voto_final_ponderado,
    rs.tiempo
FROM registro_senales rs
JOIN activos a ON a.id = rs.activo_id
WHERE rs.tiempo > NOW() - INTERVAL '10 minutes'
ORDER BY rs.tiempo DESC;
```

**Esperado:**
- `voto_macro` tiene valores distintos de NULL y distintos entre activos
- Para XAUUSD: voto_macro ≈ 0.0 (fuerzas opuestas — ver memory/project_macro_worker.md)
- Para EURUSD: voto_macro negativo (Fed Hawkish + Dolar Hegemonico = DOWN para EUR)
- Para US30/USTEC: voto_macro negativo (todos los regimenes apuntan DOWN)
- Para XTIUSD: voto_macro positivo (Guerra Iran = UP para petroleo)

**Si voto_macro es NULL en todas las filas:**
→ La columna existe pero el INSERT falla silenciosamente
→ Revisar: `SELECT * FROM registro_senales ORDER BY tiempo DESC LIMIT 3;`
→ Buscar error en logs: `grep "guardar_senal\|voto_macro" /opt/aurum/logs/aurum.log`

---

## Paso 3 — Verificar Lab Cripto evaluando

```sql
-- Señales del Lab Cripto (id=7)
SELECT
    a.simbolo,
    ls.decision_gerente,
    ls.voto_tendencia,
    ls.voto_nlp,
    ls.voto_macro,
    ls.voto_final_ponderado,
    ls.umbral_usado,
    ls.tiempo
FROM lab_senales ls
JOIN activos a ON a.id = ls.activo_id
WHERE ls.lab_id = 7
ORDER BY ls.tiempo DESC
LIMIT 10;
```

**Esperado:**
- Filas para BTCUSD y/o ETHUSD en las primeras horas
- `voto_macro` ≈ -0.83 a -0.85 en ambos (bear market + guerra + Fed)
- `decision_gerente` = IGNORADO en la mayoría (el umbral 0.55 es alto)
- Si alguna señal pasa el umbral → aparecerá como EJECUTADO y habrá fila en lab_operaciones

**Si lab_senales está vacía después de 2-3 ciclos:**
```sql
-- Verificar que el lab tiene activos asignados con sus IDs correctos
SELECT la.lab_id, la.activo_id, a.simbolo, la.estado
FROM lab_activos la
JOIN activos a ON a.id = la.activo_id
WHERE la.lab_id = 7;

-- Verificar que los votos llegan al LabEvaluator (activos en la union query)
SELECT DISTINCT a.simbolo
FROM activos a
WHERE a.id IN (
    SELECT id FROM activos WHERE estado_operativo = 'ACTIVO'
    UNION
    SELECT la.activo_id FROM lab_activos la
    JOIN laboratorios l ON l.id = la.lab_id
    WHERE la.estado = 'ACTIVO' AND l.estado = 'ACTIVO'
);
-- BTCUSD y ETHUSD deben aparecer en este resultado
```

---

## Paso 4 — Verificar que los activos cripto no crashean workers

BTCUSD y ETHUSD son nuevos. Algunos workers pueden no tener datos históricos suficientes
(TrendWorker necesita velas, HurstWorker necesita serie de precios, etc.)

```bash
# Buscar errores específicos de cripto en logs
grep -i "BTCUSD\|ETHUSD\|ERROR\|Traceback" /opt/aurum/logs/aurum.log | tail -30
```

**Posibles problemas y soluciones:**

| Error | Causa | Fix |
|-------|-------|-----|
| `copy_rates_from_pos returned None` | MetaAPI no tiene historial de BTCUSD en ese timeframe | TrendWorker retorna 0.0 — aceptable |
| `KeyError: 'BTCUSD'` en CrossWorker | CrossWorker no tiene correlaciones para cripto | Agregar manejo de None |
| `division by zero` en HurstWorker | Serie de precios muy corta (< 20 velas) | HurstWorker retorna 0.5 neutral — aceptable |
| `CANCELADO_RIESGO` por volatilidad extrema | ATR de BTC enorme comparado con su media de 0 | Primer ciclo esperado — se normaliza |

---

## Paso 5 — Verificar MacroBar en el dashboard

Abrir el dashboard → todas las páginas deben mostrar la barra superior con los 5 regimenes:

```
MacroSensor  🔴 Guerra Iran  🔴 Fed Hawkish  🔴 Recesion Europea  🔴 Dolar Hegemonico  🔴 BTC Bear Post-Halving
```

- Click en cualquier chip → modal con razonamiento + activos afectados con flechas ▲▼
- Las flechas deben tener color: ▲ verde, ▼ rojo

---

## Paso 6 — Verificar Tab Lab en el dashboard

Abrir dashboard → tab "Lab" (o /lab):

- Lab Cripto aparece con estado ACTIVO (borde verde)
- Métricas primarias: trades=0, win_rate=—, profit_factor=—, ROE=+0.00%
- Balance virtual: $3,000.00
- Activos: BTCUSD, ETHUSD
- Barra MacroSensor visible con los regimenes

Después de algunos ciclos:
- Contador de trades sube
- Botón "Ver últimas operaciones" muestra filas con badge SIM
- Precios de BTC muestran 2 decimales (no 4)

---

## Paso 7 — Verificar impacto del MacroWorker en decisiones de producción

Comparar el veredicto con y sin el ajuste macro para entender el impacto real.

```sql
-- Ver ultimas señales con detalle de votos
SELECT
    a.simbolo,
    rs.voto_tendencia   as trend,
    rs.voto_nlp         as nlp,
    rs.voto_sniper      as sniper,
    rs.voto_macro       as macro,
    rs.voto_final_ponderado as veredicto,
    rs.decision_gerente as decision,
    rs.tiempo
FROM registro_senales rs
JOIN activos a ON a.id = rs.activo_id
WHERE rs.tiempo > NOW() - INTERVAL '2 hours'
ORDER BY rs.tiempo DESC
LIMIT 20;
```

**Señal de que funciona correctamente:**
- Activos con sesgo RISK_OFF (USTEC, US30, EURUSD) tienen veredicto más negativo que antes
- Activos con sesgo RISK_ON (XTIUSD, XBRUSD) tienen veredicto más positivo
- XAUUSD tiene impacto macro ≈ 0 (neutro — fuerzas opuestas)

---

## Paso 8 — Monitoreo sostenido (primeras 2 horas de mercado)

```bash
# Performance del LabEvaluator (debe ser < 2000ms)
grep "LAB.*Ciclo evaluacion" /opt/aurum/logs/aurum.log | tail -10

# Si supera 2000ms → alerta ya implementada en el codigo
grep "LAB.*ALERTA.*supero 2000ms" /opt/aurum/logs/aurum.log
```

**Esperar al menos 30 minutos de mercado abierto antes de sacar conclusiones.**
El primer ciclo puede ser lento por cold start de MetaAPI + carga de historial de BTCUSD.

---

## Criterios de éxito

| Criterio | Verificación |
|----------|-------------|
| Bot no crashea con nuevos activos cripto | 0 Tracebacks relacionados con BTCUSD/ETHUSD |
| MacroWorker vota en producción | voto_macro != 0 en registro_senales |
| Lab Cripto genera señales | lab_senales tiene filas para lab_id=7 |
| voto_macro lab ≈ -0.85 en BTC | Confirmado en lab_senales |
| LabEvaluator < 2000ms | grep en logs |
| Dashboard Lab carga sin error | Tab /lab responde con datos |
| MacroBar visible en todas las páginas | 5 chips de regimenes visibles |

---

## Criterios de acción inmediata (rollback parcial)

**Si el bot crashea en cada ciclo:**
```bash
sudo systemctl stop aurum-core
# Revertir manager.py al commit anterior: git revert 052f022
sudo systemctl start aurum-core
```

**Si solo Lab Cripto da error (producción OK):**
```sql
-- Pausar el lab para que no afecte el ciclo
UPDATE laboratorios SET estado='PAUSADO' WHERE id=7;
```

**Si voto_macro rompe el INSERT de registro_senales:**
```sql
-- La columna tiene DEFAULT 0.0, no debería pasar
-- Verificar: SELECT COUNT(*) FROM registro_senales WHERE voto_macro IS NULL;
```

---

## Estado
- Creado: 2026-03-21
- Pendiente ejecutar: Lunes apertura mercado (Domingo ~22:00 UTC)
- Responsable: operador (maiko)
