---
name: Lab Cripto — Razonamiento de configuración
description: Por qué el Lab Cripto está configurado así — ciclo halving, peso de noticias en bear market, lógica de workers
type: project
---

## Contexto macro cripto (Marzo 2026)

### Ciclo Halving BTC
- Halving Abril 2024: recompensa 6.25 → 3.125 BTC/bloque
- Pico histórico post-halving: 12-18 meses después = Abril-Octubre 2025
- Marzo 2026 = fase distribución/corrección bear market
- **Mínimo de ciclo esperado: Octubre 2026** (análisis fractal histórico)
- Bear markets post-halving históricos: -70% a -80% desde ATH
- Implicación: sesgo SHORT/SELL hasta Q4 2026. Rebotes = oportunidades de venta.
- Almacenado en BD: regimenes_macro id=5 "BTC Ciclo Bear Post-Halving 2025-2026" peso=0.80

### Regímenes macro activos que afectan cripto
- Guerra Irán RISK_OFF (0.95) → instituciones venden crypto primero en crisis extrema
- Dólar Hegemónico RISK_OFF (0.85) → correlación inversa DXY↔BTC es la más fuerte en macro
- Fed Hawkish RISK_OFF (0.80) → BTC/ETH no pagan interés, treasuries al 5%+ más atractivos
- Net: entorno muy desfavorable para LONG en cripto

## Configuración de workers — razonamiento

### Por qué Trend 0.60 (el más alto)
En bear market, la tendencia bajista es la señal más confiable y persistente.
Los rebotes son técnicos y temporales — el Trend Worker los filtra correctamente.

### Por qué NLP 0.25 (bajo)
En bear market, las noticias tienen impacto decreciente:
- El mercado descuenta el mismo estímulo cada vez menos (Trump tariffs: 1a vez -15%, 2a vez -5%, 3a vez casi nada)
- Lo que mueve cripto en bear market (en orden de impacto real):
  1. Powell/FOMC → ya capturado por MacroSensor (Fed Hawkish)
  2. Bolsas caen fuerte → capturado por CrossWorker (SPX/DXY)
  3. Colapso de exchange (FTX-style) → aparece como noticia impacto 10
  4. Ban regulatorio masivo → aparece como noticia impacto alto
  5. Tweet de Elon → imposible capturar sistemáticamente
  6. Noticias cripto genéricas → impacto casi nulo en bear
- El NLP al 0.25 solo activa en eventos de cola extremos. En el día a día no mueve la aguja.

### Por qué Sniper 0.15
Más peso que en metales porque la volatilidad de cripto hace más importante el timing de entrada.
Los wicks en BTC/ETH pueden activar SL y regresar — el Sniper ayuda a evitar entradas en picos locales.

## Parámetros y su razonamiento

- **umbral 0.55** (vs 0.45 producción): cripto da muchas falsas señales, necesita alta convicción
- **ratio_tp 4.0**: BTC puede moverse $3,000-5,000 en un día. TP ambicioso es correcto.
- **sl_atr_multiplier 2.0**: doble que metales — los wicks en cripto son letales con SL ajustado
- **spread 80 pips**: spread real BTC/ETH puede dispararse en momentos de stress
- **riesgo 1.0%**: conservador — la volatilidad ya amplifica el riesgo intrínsecamente
- **filtro correlación ON**: BTC y ETH tienen correlación ~90%, no abrir ambos simultáneamente

## Feeds RSS cripto en news_hunter
Agregados: CoinDesk, CoinTelegraph, The Block
Propósito: detectar eventos de cola (colapso exchange, ban regulatorio) no noticias genéricas

## Estado
- Labs creados en BD: Lab Cripto id=7, Lab Metales id=6
- Ambos en estado PAUSADO — activar manualmente cuando listos para testear
- BTC mínimo esperado Oct 2026 — revisar configuración en Q4 2026
