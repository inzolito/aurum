Contexto: Bot de trading algorítmico Python/MT5/PostgreSQL. 
La tabla de votos muestra casi todo en 0.000 en todos los workers.

SÍNTOMAS (captura de pantalla adjunta):
- Tendencia: 0.000 en 9/11 activos (solo GBPJPY=-0.800 y XAUUSD=-0.800 votan)
- NLP: 0.000 en todos excepto GBPJPY=+0.600
- Flow: 0.000 en 9/11 (solo GBPJPY=+1.000 y XAUUSD=+0.030)
- Volumen: 0.000 en todos
- Cross: 0.000 en todos
- Shield: CAIDO
- Veredicto final: 0.000 en todos → decisiones CANCELADO_RIESGO o IGNORADO

CONTEXTO CRÍTICO: Ayer funcionaba bien. Hoy tras aplicar bugfixes (FIX-NLP-02, FIX-VOL-02, FIX-CROSS-02) todo cayó a cero.

TAREA:
1. Lee los archivos: workers/worker_trend.py, workers/worker_volume.py, workers/worker_cross.py, workers/worker_nlp.py, config/db_connector.py
2. Ejecuta: SELECT simbolo, simbolo_broker, estado_operativo FROM activos ORDER BY simbolo; para ver el estado real de la BD
3. Busca la causa raíz de por qué los workers retornan 0 — revisa especialmente:
   - worker_trend.py: ¿obtiene velas correctamente? ¿usa simbolo_broker con sufijo _i?
   - worker_volume.py: ¿el fix de bid/ask funciona? ¿precio_actual != 0?
   - worker_cross.py: ¿el sensor SPXUSD_i devuelve datos reales?
   - worker_nlp.py: ¿el UPSERT con ON CONFLICT funciona? ¿hay filas en cache_nlp_impactos?
   - db_connector.py: ¿leer_cache_nlp filtra por TTL correctamente?
4. Muestra los errores reales con prints de diagnóstico antes de corregir
5. Corrige solo lo que está roto, no refactorices lo que funciona
6. Verifica que GBPJPY vota (funciona parcialmente) — úsalo como caso de prueba para entender qué tienen los activos que votan vs los que no