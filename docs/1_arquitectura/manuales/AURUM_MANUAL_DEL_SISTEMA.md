# Aurum — Manual del Sistema

Este documento constituye la guía conceptual y operativa para interpretar el cerebro del bot. Aurum no es un simple cruce de medias móviles; es un **ensamble de inteligencias múltiples** (Trabajadores u "Obreros") donde cada uno es especialista en un dominio del mercado. El Gerente Central recopila sus análisis y decide si disparar, bloquear o simular.

A continuación, se describen los componentes principales del análisis estructural, técnico y fundamental.

---

## 1. El Obrero Juez de Persistencia (Hurst)

El **Exponente de Hurst** es una herramienta matemática potente que el bot utiliza para medir la "memoria" del mercado. En términos sencillos, le dice a Aurum si el precio se está moviendo con un propósito (tendencia) o si solo está dando tumbos al azar (ruido).

### ¿Cómo lo calcula el bot?
1. **Toma una gran muestra de datos:** Cada vez que evalúa, el bot descarga y analiza las últimas **1,024 velas de 1 minuto (M1)** del activo.
2. **Análisis de Rango Rescalado (R/S):** Divide esas 1,024 velas en fragmentos más pequeños (de 20, 40, 80... hasta 512 velas).
3. En cada fragmento compara cuánto se ha movido el precio desde el inicio del fragmento frente a cuánto ha fluctuado en su interior (es decir, compara el desplazamiento real contra el "ruido" o volatilidad).
4. El resultado final de todos estos cálculos es un único número que va, por lo general, entre 0 y 1. Se le llama **Exponente H**.

### ¿Qué significan los resultados para Aurum?

Aurum divide el mercado en tres estados basados en el valor de ese Exponente H:

#### 1. RUIDO (Hurst entre 0.45 y 0.55) ⚠️ *Bloqueado*
Significa que el mercado es un "Paseo Aleatorio" (Random Walk). Lo que hizo el precio hace 5 minutos no tiene ninguna correlación ni efecto predictivo sobre lo que hará los próximos 5 minutos. Es un mercado lateral, sin dirección clara, donde operar es como tirar una moneda al aire.

#### 2. ANTIPERSISTENTE (Hurst < 0.45) 🛑 *Bloqueado*
Significa que el mercado está en "reversión a la media" o haciendo *whipsaws* (latigazos). Si el precio sube en una vela, es altamente probable que baje en la siguiente y viceversa. Entrar en compra aquí a menudo termina en un stop-loss clavado al tick antes de que el precio regrese. 

#### 3. PERSISTENTE (Hurst > 0.55) 🟢 *Zona de Disparo*
A esto es lo que el bot llama **PERSISTENTE**. Significa que la serie de precios tiene "memoria a largo plazo". 
* **Si el precio viene subiendo**, es matemáticamente probable que **siga subiendo**.
* **Traducción para el bot:** Hay dinero institucional moviendo el activo en una dirección clara. Aquí es cuando hay una tendencia estructural y los sistemas seguidores de tendencia (como el filtro "Trend" y el "Veredicto" general del ensamble) tienen las máximas probabilidades de ganar.

**En conclusión:** 
El bot no pregunta simplemente *"¿Está subiendo o bajando el precio?"*. Antes de siquiera mirar si hay oportunidad de comprar, el bot le pregunta a las matemáticas: ***"¿Vale la pena operar este mercado en este momento?"***. Si el Hurst no dice **PERSISTENTE**, el mercado es un campo minado impredecible y el bot prefiere preservar el capital.

---

## 2. Los Pilares del Veredicto (Obreros de Votación)

Cuando el mercado tiene el "Pase" matemático de Hurst, el Gerente convoca a votación a los 3 obreros principales. Sus votos van de `-1.0` (Fuerte Venta) a `+1.0` (Fuerte Compra). El gerente pondera estos votos para obtener el `Veredicto`.

- **TrendWorker (TENDENCIA):** 
  Evalúa el "momentum" puramente técnico en distintos marcos temporales. Utiliza distancias a Medias Móviles Exponenciales (EMAs) y métricas de aceleración (RSI). Es el obrero clásico.
- **NLPWorker / IA (MACRO/SENTIMIENTO):**
  Lee, procesa y resume las noticias económicas globales urgentes (Bloomberg, Reuters, ForexLive) utilizando el modelo de Lenguaje Gemini. Traduce el texto fundamental ("La Fed subirá tasas", "Guerra en Medio Oriente") en un flujo numérico direccional matemático, actuando como el cerebro fundamental del ensamble.
- **StructureWorker (SNIPER / SMC):**
  Identifica zonas de liquidez institucionales. Busca Conceptos de Dinero Inteligente (SMC), como *Order Blocks* (OBs) y cambios en la estructura del mercado. Revisa que no estemos comprando en medio de la nada, sino apoyados en un bloque institucional fuerte.

**Umbral de Disparo:** La sumatoria ponderada de estos tres votos debe superar una certeza mínima (usualmente `0.45`). Si llega a `0.478`, el sistema grita **"DISPARA"**.

---

## 3. Guardianes de la Cuenta (Penalizaciones y Bloqueos)

Incluso si el Veredicto es alto y el mercado es Persistente, Aurum puede decidir cancelar todo en el último segundo. A esto se le llama **Guardianes de la cuenta**:

- **Filtro F1 (Agotamiento de Tendencia):**
  Si el TrendWorker vota muy alto (`>= 0.60`) indicando un momentum extremo y a la vez el Hurst es `PERSISTENTE`, el bot sabe que la tendencia lleva demasiado tiempo existiendo. El riesgo de reversión letal es extremo. Se cancela el trade antes de ser "atrapados en la cima".
  
- **Veto de Volatilidad (ATR):**
  El bot compara el tamaño de la última vela contra el promedio de las últimas 10 previas. Si la vela actual es el doble de grande (explosión >= 200%), asume que una noticia no catalogada sacudió los mercados. Veta toda operativa hasta que se asiente el polvo.

- **CrossWorker (Intermarket & Black Swan):**
  El CrossWorker es el guardián de la correlación macro. Lee continuamente índices globales refugio (como el Índice del Dólar - DXY, Petróleo o S&P 500). Si el DXY explota, declara estado de **"Cisne Negro" (Black Swan)**, elevando temporalmente las exigencias (Umbral sube al `0.60`) para operar cualquier activo en el mundo.

- **VolumeWorker (Volume Profile):**
  Hace radiografías horizontales para encontrar el *Point of Control (POC)* —el nivel de precio exacto donde ha ocurrido más volumen de transacciones—. Si estamos operando fuera del área de valor sin volumen que nos respalde, el Veredicto recibe leves penalizaciones.
