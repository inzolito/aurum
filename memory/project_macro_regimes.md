---
name: MacroSensor — Regímenes Macro
description: Sistema de contexto macro global — regímenes creados automáticamente por news_hunter/Gemini, usados por NLPWorker en cada votación de entrada
type: project
---

## Concepto
Una capa de contexto por encima de todos los workers que describe el estado macro del mundo en tiempo real. Múltiples regímenes pueden estar activos simultáneamente y se solapan. Es global — aplica a producción y a todos los modelos de laboratorio.

**Why:** El bot actualmente vota activo por activo sin saber si hay una guerra, si Powell habla mañana, o si NVIDIA publica resultados esta noche. El MacroSensor le da ese contexto a Gemini para que vote con inteligencia macro.

**How to apply:** Al implementar, los regímenes se inyectan en el prompt del NLPWorker. No requiere worker nuevo — solo enriquecer el prompt existente con los regímenes activos de BD.

---

## Tipos de Régimen

| Tipo | Ejemplos | Duración típica |
|------|----------|-----------------|
| Monetario | Powell habla, FOMC, rumor baja tasas, pausa Fed | Horas / días |
| Geopolítico | Guerra, sanciones, elecciones | Indefinido |
| Corporativo | NVIDIA earnings, Apple resultados trimestrales | Fecha fija conocida |
| Económico | CPI, NFP, datos de empleo, recesión | Variable |
| Mercado | VIX spike, dólar fuerte, crisis liquidez | Variable |

---

## Ciclo de vida de un régimen

### Ejemplo — NVIDIA Earnings:
```
[Semanas antes]  news_hunter detecta "NVIDIA reporta Q1 el 21-Mar"
                 → Gemini crea régimen: tipo=CORPORATIVO, fase=RUMOR
                 → dirección=RISK-ON tech, activos=[USTEC, US500]
                 → expira: 21-Mar 22:00 UTC
                 → razonamiento: "Mercado anticipa beat histórico. Tech sube en anticipación."

[Día de resultados] Gemini actualiza régimen a fase=DATOS
                    → dirección=VOLÁTIL, umbral elevado automáticamente

[Post-resultados buenos] Gemini crea nuevo régimen: fase=TAKE_PROFIT
                         → dirección=RISK-OFF tech (sell the news)
                         → expira: 24-48h
                         → razonamiento: "Beat confirmado pero expectativas ya descontadas. Toma de ganancias esperada."
```

### Ejemplo — Solapamiento:
```
Activos simultáneos:
- Guerra comercial EEUU-China (RISK-OFF, indefinido, peso=0.8)
- Fed pausa tasas (RISK-ON, 5 días, peso=0.6)
- Powell habla hoy (VOLÁTIL, 4h, peso=0.9)

Score resultante para USTEC: RISK-OFF moderado con alta volatilidad
```

---

## Creación automática — news_hunter

Cuando `news_hunter` procesa una noticia con Gemini, además del score de impacto (1-10), Gemini evalúa:
1. ¿Esta noticia genera o modifica un régimen macro?
2. Si sí → tipo, dirección (RISK-ON/RISK-OFF/VOLÁTIL), activos afectados, expiración estimada, razonamiento

El razonamiento se guarda en BD — es el "por qué es relevante" que se muestra en el dashboard.

---

## Nueva tabla en BD

```sql
CREATE TABLE regimenes_macro (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(30),                -- MONETARIO, GEOPOLITICO, CORPORATIVO, ECONOMICO, MERCADO
    nombre VARCHAR(100) NOT NULL,    -- "Guerra comercial EEUU-China", "NVIDIA Earnings Q1"
    fase VARCHAR(20),                -- RUMOR, DATOS, TAKE_PROFIT, ACTIVO
    direccion VARCHAR(20),           -- RISK_ON, RISK_OFF, VOLATIL
    peso DECIMAL(3,2) DEFAULT 0.5,   -- relevancia del régimen (0.0 a 1.0)
    activos_afectados TEXT,          -- "USTEC,US500,XAUUSD" (CSV o JSON)
    razonamiento TEXT,               -- explicación de Gemini de por qué es relevante
    creado_en TIMESTAMP DEFAULT NOW(),
    expira_en TIMESTAMP,             -- NULL = indefinido
    activo BOOLEAN DEFAULT TRUE,
    fuente_noticia_id INTEGER        -- referencia a la noticia que lo generó
);
```

---

## Integración con NLPWorker

En cada ciclo, antes de llamar a Gemini para votar por un activo, el NLPWorker:
1. Lee todos los regímenes activos (`activo=TRUE` y `expira_en > NOW()`)
2. Filtra los relevantes para el activo actual (por `activos_afectados`)
3. Los inyecta en el prompt:

```
"Contexto macro actual (considera esto en tu análisis):
 - [RISK-OFF, peso=0.8] Guerra comercial EEUU-China (indefinido):
   'Aranceles 25% generan huida a refugio. Favorece XAUUSD, penaliza USTEC.'
 - [VOLÁTIL, peso=0.9] Powell habla en 2h (expira hoy):
   'Mercado en espera. Alta incertidumbre direccional hasta el discurso.'

Con este contexto macro, analiza la entrada en USTEC..."
```

Gemini vota considerando TODO ese contexto. Si hay RISK-OFF fuerte, puede votar -0.60 aunque el Trend diga +0.40.

---

## Dashboard — Sección en Config

Mostrar todos los regímenes activos con:
- Badge de dirección (🔴 RISK-OFF / 🟢 RISK-ON / 🟡 VOLÁTIL)
- Nombre del régimen
- Expiración ("expira en 4h", "indefinido")
- Razonamiento completo de Gemini
- Activos afectados con flecha direccional (XAUUSD ▲, USTEC ▼)
- Posibilidad de crear régimen manualmente (usuario puede agregar contexto que Gemini no detectó)

---

## Estado
- Planificado: 2026-03-20
- Versión: V18.0 (junto con el Laboratorio)
- Pendiente: definir si news_hunter crea regímenes en el mismo loop o en uno separado
