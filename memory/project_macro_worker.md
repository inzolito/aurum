---
name: MacroWorker — Worker Pasivo de Contexto Macro
description: Diseño del MacroWorker — lee regimenes_macro de BD y devuelve voto persistente por activo. Resuelve el problema de que el contexto macro (bear market, guerra, Fed) no influye directamente en el ensemble de votos.
type: project
---

## Problema que resuelve

El sistema actual tiene dos capas de contexto macro:
1. **NLPWorker**: Gemini recibe los regimenes activos en su prompt y los considera al votar.
   - PROBLEMA: Solo activa cuando hay una noticia nueva. Entre noticias, el contexto macro
     no tiene peso en el ensemble.
2. **regimenes_macro en BD**: El bear market de BTC existe como dato pero NADIE lo vota.
   - PROBLEMA: Si hay 0 noticias ese ciclo, el voto macro = 0. Como si el bear no existiera.

**Consecuencia real:** En un bear market cripto prolongado, sin noticias ese dia, el ensemble
puede dar BUY porque Trend+Sniper ven un rebote tecnico. El contexto -bear market durante
10 meses- no tiene peso directo en la decision.

---

## Concepto del MacroWorker

Un worker PASIVO que:
- NO llama APIs externas (sin Gemini, sin MT5)
- Lee `regimenes_macro` de BD (ya en memoria/cache)
- Filtra los regimenes relevantes para el activo actual
- Calcula un voto ponderado en [-1.0, +1.0]
- Devuelve ese voto CADA CICLO, sea que haya noticias o no

**Es el unico worker que persiste su opinion durante semanas o meses.**
Todos los demas workers votan segun el momento. El MacroWorker vota segun el contexto estructural.

---

## Logica de calculo del voto

Cada regimen en `regimenes_macro` tiene:
- `direccion`: RISK_ON, RISK_OFF, VOLATIL
- `peso`: 0.0 a 1.0
- `activos_afectados`: JSON con simbolo y direccion especifica por activo
  Ejemplo: [{"simbolo":"XAUUSD","dir":"UP"},{"simbolo":"USTEC","dir":"DOWN"},{"simbolo":"BTCUSD","dir":"DOWN"}]

**Algoritmo:**
```python
def votar(self, simbolo: str, regimenes: list) -> float:
    contribuciones = []
    for r in regimenes:
        # Buscar si este activo esta afectado
        activos = json.loads(r['activos_afectados'] or '[]')
        match = next((a for a in activos if a['simbolo'] == simbolo), None)

        if match:
            # Direccion especifica para este activo
            dir_activo = +1.0 if match['dir'] == 'UP' else -1.0
            contribuciones.append(dir_activo * r['peso'])
        elif r['activos_afectados'] is None:
            # Regimen global (afecta a todos)
            dir_global = -1.0 if r['direccion'] == 'RISK_OFF' else (+1.0 if r['direccion'] == 'RISK_ON' else 0.0)
            contribuciones.append(dir_global * r['peso'])
        # Si activos_afectados tiene lista pero no incluye este simbolo → no aplica

    if not contribuciones:
        return 0.0

    # Promedio ponderado normalizado a [-1, +1]
    voto = sum(contribuciones) / len(contribuciones)
    return max(-1.0, min(1.0, voto))
```

---

## Ejemplos con regimenes actuales en BD

### BTCUSD en Marzo 2026

| Regimen | Peso | Dir para BTC | Contribucion |
|---------|------|--------------|--------------|
| Guerra Iran | 0.95 | DOWN (instituciones venden cripto en crisis) | -0.95 |
| Dolar Hegemonico | 0.85 | DOWN (DXY ↑ = BTC ↓, correlacion inversa) | -0.85 |
| Fed Hawkish | 0.80 | DOWN (treasuries 5%+ vs BTC sin yield) | -0.80 |
| Aranceles Trump | 0.75 | DOWN (RISK_OFF global) | -0.75 |
| BTC Bear Post-Halving | 0.80 | DOWN (ciclo estructural) | -0.80 |
| **VOTO MACRO** | | | **-0.83** |

Resultado: antes de ver ningun grafico, el MacroWorker ya vota -0.83 en BTC.
Para que el ensemble dispare un LONG, el resto de workers necesitarian compensar ese -0.83.
Con peso_macro = 0.30 en el ensemble → necesita Trend + NLP + Sniper muy alcistas.

### XAUUSD en Marzo 2026

| Regimen | Peso | Dir para XAUUSD | Contribucion |
|---------|------|-----------------|--------------|
| Guerra Iran | 0.95 | UP (refugio) | +0.95 |
| Dolar Hegemonico | 0.85 | DOWN (DXY ↑ = oro ↓ en terminos nominales) | -0.85 |
| Fed Hawkish | 0.80 | DOWN (oro sin yield vs treasuries) | -0.80 |
| Aranceles Trump | 0.75 | UP (miedo → refugio) | +0.75 |
| BTC Bear Post-Halving | 0.80 | N/A (no aplica a oro) | sin contribucion |
| **VOTO MACRO** | | | **+0.01 (neutro)** |

Resultado: oro tiene fuerzas opuestas equilibradas → MacroWorker neutro → el tecnico manda.
Tiene sentido: oro esta en tension entre ser refugio vs costo de oportunidad de tasas altas.

---

## Peso en el ensemble

El MacroWorker se suma al ensemble ponderado en manager.py y lab_evaluator.py.

**Produccion (propuesta):**
- `MACRO.peso_voto = 0.20` — suficiente para sesgar sin dominar

**Lab Cripto:**
- `MACRO.peso_voto = 0.35` — el contexto macro es muy relevante en cripto

**Lab Metales:**
- `MACRO.peso_voto = 0.25` — oro tiene mas drivers propios (refugio, joyeria, bancos centrales)

Formula actualizada:
```
veredicto = Trend*0.50 + NLP*0.50 + Macro*0.20 + Sniper*0.15 (normalizado)
```
O con pesos absolutos y normalizacion posterior.

---

## Diferencia con NLPWorker+MacroSensor actual

| | NLPWorker (con regimenes en prompt) | MacroWorker (propuesto) |
|--|-------------------------------------|-------------------------|
| Cuando vota | Solo cuando hay noticia nueva | CADA CICLO siempre |
| Quien decide | Gemini (puede ignorar el contexto) | Algoritmo determinista |
| Latencia | 2-3s (llamada API Gemini) | <1ms (query BD cache) |
| Costo | Tokens de Gemini | Cero |
| Persistencia | No — el contexto se "olvida" entre noticias | Si — el bear market vota 10 meses |
| Complementariedad | Vota la coyuntura de la noticia | Vota el fondo estructural |

Son complementarios, no excluyentes. NLP captura el choque de la noticia.
MacroWorker captura el regimen persistente.

---

## Implementacion — que requiere

### 1. Nuevo archivo: workers/macro_worker.py
- Lee cache de regimenes (actualizado desde BD cada ciclo por db_connector)
- Metodo votar(simbolo) → float [-1, +1]
- Sin dependencias externas (cero latencia adicional)

### 2. Columna nueva en registro_senales
```sql
ALTER TABLE registro_senales ADD COLUMN voto_macro NUMERIC(4,3);
ALTER TABLE lab_senales ADD COLUMN voto_macro NUMERIC(4,3);
```

### 3. Parametro en BD
```sql
INSERT INTO parametros_sistema (nombre, valor, descripcion) VALUES
('MACRO.peso_voto', '0.20', 'Peso del MacroWorker en el ensemble');
```

### 4. manager.py — agregar al ensemble
```python
voto_macro = self.macro_worker.votar(simbolo, regimenes_activos)
# Agregar a la formula de veredicto
```

### 5. lab_evaluator.py — usar peso propio del lab
```python
peso_macro = float(lab_params.get('MACRO.peso_voto', '0.20'))
voto_macro = self.macro_worker.votar(simbolo, regimenes_activos)
```

---

## Impacto en performance

- MacroWorker NO llama APIs → 0ms adicionales en latencia
- regimenes_macro se cachean en memoria (ya implementado en db_connector)
- 1 query extra por ciclo para actualizar el cache → <5ms
- Total overhead: insignificante

---

## Estado
- Disenado: 2026-03-20
- Decision: PENDIENTE — analizar si implementar en V18.1 o junto con V18
- Bloqueante: requiere migracion (columna voto_macro en registro_senales y lab_senales)
- Prioridad: ALTA para Lab Cripto — sin MacroWorker el lab ignora el bear market en el ensemble
