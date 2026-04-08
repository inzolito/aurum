# Propuesta: Simulador de Entradas Históricas (Backtester de Señales)

## 1. Objetivo General
Desarrollar una herramienta (scripts + potencial integración UI) que permita evaluar rápidamente qué hubiera pasado si el sistema hubiera tomado una decisión de trading en el pasado que, por algún motivo (filtros de seguridad, fuera de horario, spread alto), fue rechazada o ignorada.

Esto permitirá al equipo:
- Validar si los filtros de seguridad (como el F1 de Hurst + Trend) están salvando a la cuenta de pérdidas.
- Descubrir "falsos positivos" en los bloqueos (operaciones que hubieran sido ganadoras pero el sistema bloqueó por ser muy conservador).
- Ajustar umbrales y modelos matemáticos de riesgo con data exacta tick-a-tick o vela-a-vela.

## 2. Arquitectura de la Solución

El simulador encapsulará la lógica que usamos para investigar el trade de `AUDJPY`, pero de forma parametrizada y reutilizable.

### 2.1 Entradas Requeridas (Inputs)
Para simular un trade, la herramienta tomará los siguientes parámetros:
- **Símbolo (Activo):** Ej. `AUDJPY`
- **Fecha y Hora Exacta:** Ej. `2026-03-31 17:38:00` (Debe soportar zona horaria de Santiago o UTC).
- **Dirección:** `COMPRA` o `VENTA`
- **Veredicto o Nivel de Riesgo (Opcional):** Para calcular el lotaje, Stop Loss (SL) y Take Profit (TP) utilizando dinámicamente el `RiskModule` actual de Aurum. En caso de no proveerse, se pueden pasar manualmente el SL y TP.

### 2.2 Origen de Datos (Data Source)
1. **Primario (MetaTrader 5):** Reutilizando el `MT5Connector`, la herramienta hará un fetching histórico (usando la función `copy_rates_range` en temporalidad de 1 Minuto `M1` o `M5`) desde el timestamp de entrada hacia el futuro (ej. las siguientes 24 horas).
2. **Fallback (Yahoo Finance API):** Si MT5 no está disponible o el servidor falla, el módulo de Request a Yahoo Finance utilizado durante la emergencia puede entrar como plan de contingencia para índices y forex mayores.

### 2.3 Motor de Simulación
El motor iterará sobre las velas obtenidas posteriores a la fecha de entrada:
1. Captura el precio de entrada (`Open` de la vela correspondiente al minuto exacto).
2. Define `Take Profit` y `Stop Loss` (Vía `RiskModule` o inputs manuales).
3. Evalúa en un loop cada vela subsiguiente:
   - ¿El precio `Low` / `High` tocó el SL primero? -> **Perdida (Hit SL)**
   - ¿El precio `High` / `Low` tocó el TP primero? -> **Ganancia (Hit TP)**
4. Registra métricas adicionales:
   - **Maximum Adverse Excursion (MAE):** Cuánto en contra llegó a estar el trade antes de cerrarse.
   - **Maximum Favorable Excursion (MFE):** Cuánto a favor llegó a estar.
   - **Tiempo en el mercado:** Cuánto tardó en tocar el SL o TP.

## 3. Fases de Implementación Propuestas

### Fase 1: Script CLI (`scripts/simulador_historico.py`)
Un script en Python puro que acepte argumentos por consola o funcione modificando unas variables arriba.
**Uso esperado:**
```bash
python scripts/simulador_historico.py --activo AUDJPY --fecha "2026-03-31 17:38" --direccion COMPRA --veredicto 0.478
```
*Output en consola indicando si fue Hit TP, Hit SL, y gráficas en terminal.*

### Fase 2: Módulo Core (`core/simulator.py`)
Convertir el script en una clase orientada a objetos (`TradeSimulator`) que pueda ser llamada por otros componentes del Bot (por ejemplo, para que el bot simule automáticamente todos los trades bloqueados durante la semana y mande un reporte el domingo).

### Fase 3: Integración en el Dashboard
En la interfaz web Blanca (Lab o Monitor), agregar un botón de 🧪 **"Simular Escenario"** al lado de cada voto rechazado en la bitácora, para que con un solo clic los usuarios puedan ver un pop-up que dibuja la gráfica y el resultado de esa oportunidad perdida.

## 4. Archivos a crear/modificar
- `[NUEVO]` `scripts/simulador_historico.py`
- `[OPCIONAL]` `core/simulator.py` (si se avanza a la Fase 2)
- Reutilizará: `config/mt5_connector.py` y `core/risk_module.py`
