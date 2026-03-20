---
name: Plan V18.5 — Entradas en Soporte/Resistencia
description: Plan de implementación para V18.5: entrada en pullback a nivel clave en vez de a precio de mercado (movido desde V18 — el Laboratorio de Activos pasa a ser V18)
type: project
---

## Concepto
En vez de ejecutar órdenes a precio de mercado cuando el veredicto supera el umbral, el bot identifica el nivel clave más cercano (EMA21, FVG del Sniper, pivote) y espera que el precio llegue a ese nivel antes de entrar.

## Por qué es sólido
- Estrategia de "Pullback Entry" / "Trend Following with Retracement" — una de las más estudiadas
- Mejora win rate ~15-25% según estudios en forex e índices
- El bot ya tiene todo: EMA21 (TrendWorker), FVG/BOS (SniperWorker), ATR
- Resuelve el problema observado el 19-Mar: entradas en medio de velas o en techos locales

## Lógica de implementación
1. Veredicto supera umbral (0.45) → calcular nivel_entrada
2. Para COMP: nivel = EMA21 (o borde inferior de FVG alcista si Sniper tiene estructura)
3. Para VENT: nivel = EMA21 (o borde superior de FVG bajista)
4. Si precio ya está dentro de MARGEN_ENTRADA del nivel → ejecutar inmediatamente
5. Si no → estado "BUSCANDO_ENTRADA" por máx N_CICLOS_ESPERA ciclos
6. Si precio llega al nivel dentro del timeout → ejecutar
7. Si no llega → abandonar señal

## Parámetros configurables en BD (parametros_sistema)
- `GERENTE.margen_entrada_pct`: cuánto % por encima/debajo del nivel exacto se acepta la entrada. Ej: 0.1% → si nivel es 5100, acepta entre 5095 y 5105. Default sugerido: 0.15%
- `GERENTE.ciclos_espera_entrada`: cuántos ciclos de 60s esperar antes de abandonar. Default: 5 (5 minutos)
- `GERENTE.usar_pullback`: flag on/off para activar/desactivar esta lógica. Default: 1 (activo)

## Archivos a modificar
- `core/manager.py`: agregar lógica de "BUSCANDO_ENTRADA" y verificación de nivel
- `core/risk_module.py`: pasar nivel_entrada calculado en vez de precio_actual
- `config/db_connector.py`: leer nuevos parámetros
- BD: INSERT en parametros_sistema los 3 nuevos parámetros

## Estado
- Planificado el 2026-03-19
- Movido a V18.5 el 2026-03-20 — el Laboratorio de Activos pasa a ocupar V18
- Versión: V18.5

**Why:** Todos los trades del 19-Mar se perdieron por entradas a destiempo (compras en techos nocturnos, ventas en pisos). La dirección de los workers era correcta pero el timing era pésimo.
**How to apply:** Al iniciar la implementación, revisar primero cómo manager.py maneja el veredicto → ejecución, y cómo TrendWorker expone EMA21.
