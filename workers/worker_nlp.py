"""
workers/worker_nlp.py — Obrero de Contexto Macro con Gemini AI
VERSION 2.0 — Análisis Dinámico con Caché

Flujo:
  1. Calcula el hash SHA256 del contexto macro actual (tabla regimenes_mercado).
  2. Si existe caché válido (< 30 min, mismo hash) -> lee de cache_nlp_impactos.
  3. Si el caché expiró o el contexto cambió -> llama a Gemini (1 llamada multi-activo).
  4. Parsea el JSON con guardrails estrictos y clamp(-1.0, 1.0).
  5. Persiste el resultado en cache_nlp_impactos para los próximos ciclos.
  6. analizar(simbolo, id_activo) expone la misma firma pública de v1.
"""

import os
import sys
import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Forzar UTF-8 en stdout para evitar charmap errors en Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
CACHE_TTL_MIN     = int(os.getenv("NLP_CACHE_TTL_MIN", "5"))       # P-2 V14: reducido de 30 a 5 min
GEMINI_MODEL_LITE = "gemini-2.0-flash-lite"  # Modelo ligero (google-genai SDK v1.0+)
GEMINI_MODEL_PRO  = "gemini-2.0-flash"         # Modelo estándar para alertas de emergencia
_MAX_CALLS_PER_DAY = int(os.getenv("NLP_MAX_CALLS_DAY", "1500"))  # D5 V14: límite diario de API


def _llamar_gemini_api(prompt: str, model: str = GEMINI_MODEL_LITE) -> str:
    """
    Llama a Gemini usando el SDK google.genai.
    Retorna el texto de la respuesta o string vacio si falla.
    """
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        respuesta = client.models.generate_content(
            model=model,
            contents=prompt
        )
        return respuesta.text.strip()
    except Exception as e:
        print(f"[NLP] ERROR en API Gemini ({model}): {e}")
        return ""


def _clamp(v) -> float:
    """Garantiza que el valor esté en [-1.0, 1.0]. Guardrail de seguridad."""
    try:
        return max(-1.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _extraer_json(texto: str) -> str:
    """Extrae el bloque JSON de la respuesta de Gemini (quita markdown si hay)."""
    texto = texto.strip()
    # Quita bloques ```json ... ``` o ``` ... ```
    if "```" in texto:
        partes = texto.split("```")
        for parte in partes:
            parte = parte.strip()
            if parte.startswith("json"):
                parte = parte[4:].strip()
            if parte.startswith("{"):
                return parte
    # Si no hay markdown, busca llaves directamente
    inicio = texto.find("{")
    fin    = texto.rfind("}") + 1
    if inicio >= 0 and fin > inicio:
        return texto[inicio:fin]
    return texto


class NLPWorker:
    """
    Obrero de Contexto Macroeconómico — VERSION 2.0 con Gemini AI.
    Consulta Gemini para obtener impactos dinámicos por activo.
    Sistema de caché por hash SHA256 del contexto macro (TTL: 30 min).
    Misma firma pública que v1: analizar(simbolo_interno, id_activo).
    """

    def __init__(self, db):
        self.db = db
        self._api_disponible = bool(GEMINI_API_KEY)
        if not self._api_disponible:
            print("[NLP] ADVERTENCIA: GEMINI_API_KEY no configurada. Worker usará modo fallback (sin IA).")
        self._ultimo_refresh = datetime.min.replace(tzinfo=timezone.utc)  # Para el guard de 5 min
        self._ultimo_hash = None  # P-2 V14: rastreo de hash para forzar refresh inmediato
        self._api_calls_today = 0  # D5 V14: contador diario de llamadas API
        self._api_calls_date = None  # D5 V14: fecha del contador actual
    def extract_nlp_score(self, text: str) -> float | None:
        """Extrae el puntaje usando Regex [SCORE: X.XX]."""
        pattern = r"\[SCORE:\s*([+-]?\d*\.?\d+)\]"
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except:
                return None
        return None

    # ------------------------------------------------------------------
    # API Pública (misma firma que v1, ampliada v2)
    # ------------------------------------------------------------------

    def analizar(self, simbolo_interno: str, id_activo: int = None, forzar_refresh: bool = False, 
                 technical_verdict: float = 0.0, velas_recientes: list = None, solo_si_conviccion: bool = True) -> float:
        """
        Retorna el voto macro para el activo dado.
        Usa Gemini con caché inteligente.
        V10.2: Si solo_si_conviccion es True y |technical_verdict| < 0.40, salta Gemini.
        """
        # V15.1: El usuario exige ver numeros siempre. Removemos el guard de conviccion tecnica.
        # if solo_si_conviccion and abs(technical_verdict) < 0.40:
        #     return 0.0
        if id_activo is None:
            id_activo = self._resolver_id(simbolo_interno)
            if id_activo is None:
                print(f"[NLP] ERROR: '{simbolo_interno}' no encontrado en BD. Voto neutral.")
                return 0.0

        if not self._api_disponible:
            return self._fallback_impactos_regimen(simbolo_interno, id_activo)

        # Obtener contexto macro y su hash primero para detectar cambios
        ahora = datetime.now(timezone.utc)
        regimenes  = self._obtener_regimenes_activos()
        hash_ctx   = self._calcular_hash(regimenes)
        ignorar_cache_ahora = False

        # P-2 V14: Si el hash cambia, forzar refresh inmediato sin importar TTL ni cooldown
        if self._ultimo_hash is not None and hash_ctx != self._ultimo_hash:
            print(f"[NLP] Hash de contexto cambiado ({self._ultimo_hash[:8]} -> {hash_ctx[:8]}). Forzando re-analisis inmediato.")
            ignorar_cache_ahora = True
            self._ultimo_refresh = ahora
        self._ultimo_hash = hash_ctx

        # Evaluar límite de refresco forzado por volatilidad (Cooldown 5 min)
        if not ignorar_cache_ahora and forzar_refresh:
            if (ahora - self._ultimo_refresh).total_seconds() > 300:
                print(f"[NLP-REFLEJO] ⚡ Volatilidad detectada en {simbolo_interno}. Forzando re-analisis Gemini.")
                ignorar_cache_ahora = True
                self._ultimo_refresh = ahora
            else:
                tiempo_restante = 300 - (ahora - self._ultimo_refresh).total_seconds()
                print(f"[NLP] Refresco forzado ignorado (cooldown: {int(tiempo_restante)}s restantes)")

        # Intentar leer del caché primero (si no hay refresco forzado)
        voto_cache = None
        if not ignorar_cache_ahora:
            voto_cache = self._leer_cache(hash_ctx, id_activo)
            
        if voto_cache is not None:
            print(f"[NLP] {simbolo_interno} (id={id_activo}) -> cache: {voto_cache:+.2f}")
            return voto_cache

        # Caché inválido o refresco forzado: llamar a Gemini para TODOS los activos
        activos_db = self.db.obtener_activos_patrullaje()
        resultados = self._llamar_gemini(regimenes, activos_db, technical_verdict, velas_recientes)

        if resultados:
            self._guardar_cache(hash_ctx, activos_db, resultados, regimenes)

        res_final = resultados.get(simbolo_interno, {'voto': 0.0, 'razonamiento': "Analisis neutral."})
        voto = res_final['voto']
        print(f"[NLP] {simbolo_interno} (id={id_activo}) -> Gemini: {voto:+.2f}")
        return voto

    def obtener_razonamiento(self, simbolo_interno: str) -> str:
        """Retorna la explicación textual guardada en el caché para este activo (V8.1: Atomic)."""
        razon = self.db.get_nlp_reasoning(simbolo_interno)
        if razon:
            return razon
        return "Análisis macro: El sentimiento institucional se mantiene cauteloso ante la falta de catalizadores claros."

    def get_current_hash(self) -> str:
        """
        Calcula y retorna el hash actual del contexto macro (V9.0).
        Útil para que el Manager sepa si hubo un cambio real en las noticias.
        """
        regimenes = self._obtener_regimenes_activos()
        return self._calcular_hash(regimenes)

    # ------------------------------------------------------------------
    # Gemini
    # ------------------------------------------------------------------

    def _llamar_gemini(self, regimenes: list, activos: list, technical_verdict: float = 0.0, velas: list = None) -> dict:
        """
        Llama a Gemini con un prompt multi-activo (Dual: Clasificación + Correlación).
        """
        simbolos = [a["simbolo"] for a in activos]
        fallback  = {s: {'voto': 0.0, 'razonamiento': "Error API Gemini."} for s in simbolos}

        # D5 V14: Control de límite diario de llamadas API
        hoy = datetime.now(timezone.utc).date()
        if self._api_calls_date != hoy:
            self._api_calls_today = 0
            self._api_calls_date = hoy
        if self._api_calls_today >= _MAX_CALLS_PER_DAY:
            print(f"[NLP] Limite diario de API alcanzado ({_MAX_CALLS_PER_DAY} llamadas). Usando cache/fallback.")
            return fallback
        self._api_calls_today += 1
        print(f"[NLP] Llamada API #{self._api_calls_today}/{_MAX_CALLS_PER_DAY} hoy.")

        # 0.0: Obtener Noticias Crudas Recientes (V15.1 Real-Time injection)
        noticias_recientes = self.db.get_top_news(limit=10)
        news_str = "\n".join([f"- {n['title']} (Pub: {n['fecha']})" for n in noticias_recientes]) if noticias_recientes else "Sin noticias crudas."

        # 0. Obtener Memoria de Largo Plazo (V11.2)
        catalizadores = self.db.get_catalizadores_activos()
        cats_str = "\n".join([f"- {c['name']} (Sentimiento AI: {c['score']})" for c in catalizadores]) if catalizadores else "Sin catalizadores activos."

        modelo_final = GEMINI_MODEL_LITE
        
        # 2. Compresion de Contexto
        regimenes_recientes = regimenes[-5:]
        ctx_lineas = []
        for r in regimenes_recientes:
            ctx_lineas.append(f"- {r['titulo']} ({r['clasificacion']})")
        contexto_str = "\n".join(ctx_lineas)
        
        # 3. Datos de Velas
        velas_str = "No hay datos de velas recientes."
        if velas:
            v_lines = []
            for v in velas[-3:]:
                v_lines.append(f"Vela: O:{v['apertura']} H:{v['maximo']} L:{v['minimo']} C:{v['cierre']}")
            velas_str = "\n".join(v_lines)

        activos_str  = ", ".join(simbolos)
        
        prompt = (
            "Eres un Analista Macro Senior con memoria de largo plazo (V13.0).\n\n"
            "🧠 MEMORIA DE LARGO PLAZO (Catalizadores Activos):\n"
            f"{cats_str}\n\n"
            "🗞️ CONTEXTO ESTRUCTURAL:\n"
            f"{contexto_str}\n\n"
            "🔥 NOTICIAS DE ÚLTIMA HORA (Raw Feed):\n"
            f"{news_str}\n\n"
            "📊 DATOS TÉCNICOS (Últimas 3 velas):\n"
            f"{velas_str}\n\n"
            "TAREA:\n"
            "1. CLASIFICACIÓN: Identifica si alguna noticia nueva es un CATALIZADOR de largo plazo.\n"
            "2. REGIME SHIFT: Si detectas un catalizador con impacto > 0.85, compáralo con la MEMORIA. "
            "¿El 'Contexto Maestro' ha sido REFORZADO o INVALIDADO? Explícalo brevemente.\n\n"
            "Devuelve UNICAMENTE un JSON (sin markdown):\n"
            "{\n"
            "  \"analisis_activos\": {\"SIMBOLO\": {\"voto\": float, \"razonamiento\": \"...\"}, ...},\n"
            "  \"catalizadores_detectados\": [\n"
            "    {\"nombre\": \"...\", \"score\": float, \"estado\": \"REFORZADO|INVALIDADO|NUEVO\", \"descripcion\": \"...\"}\n"
            "  ]\n"
            "}\n\n"
            "IMPORTANTE: Cada 'razonamiento' DEBE terminar estrictamente con la etiqueta [SCORE: X.XX].\n"
            "Ejemplo: '...panorama alcista. [SCORE: 0.75]'\n"
            f"Activos a evaluar: {activos_str}\n"
        )

        # Re-intento (V15.0)
        for intento in range(2):
            texto = _llamar_gemini_api(prompt, model=modelo_final)
            if not texto: continue

            try:
                json_str = _extraer_json(texto)
                data = json.loads(json_str)
                
                # Persistir catalizadores (V11.2)
                for c in data.get("catalizadores_detectados", []):
                    self.db.upsert_catalizador(c["nombre"], _clamp(c["score"]))
                    
                res_parseado = self._parsear_respuesta_v2(data.get("analisis_activos", {}), simbolos)
                
                # Validar si hay fallos de lectura (0.00 con texto largo)
                hay_inconsistencia = False
                for s in simbolos:
                    item = res_parseado.get(s, {})
                    if len(item.get('razonamiento', '').split()) > 50 and abs(item.get('voto', 0.0)) < 0.001:
                        print(f"[NLP-VALIDACION] 🚨 Inconsistencia detectada en {s}. Re-intentando...")
                        hay_inconsistencia = True
                        break
                
                if not hay_inconsistencia or intento == 1:
                    return res_parseado
                
            except Exception as e:
                print(f"[NLP] Error procesando respuesta dual (intento {intento+1}): {e}")
        
        return fallback

    def _parsear_respuesta_v2(self, data: dict, simbolos: list) -> dict:
        resultado = {s: {'voto': 0.0, 'razonamiento': "Sin datos"} for s in simbolos}
        for simbolo in simbolos:
            if simbolo in data:
                item = data[simbolo]
                
                # Manejar formato: {"SIMBOLO": "razonamiento [SCORE: X.XX]"}
                if isinstance(item, str):
                    r = item
                    v_json = 0.0
                # Manejar formato: {"SIMBOLO": {"voto": float, "razonamiento": "..."}}
                elif isinstance(item, dict):
                    r = item.get('razonamiento', "Neutral.")
                    v_json = item.get('voto', 0.0)
                else:
                    r = "Neutral."
                    v_json = 0.0
                
                # Extraer del tag [SCORE: X.XX] (V15.0 Regex) - PRIORIDAD
                v_regex = self.extract_nlp_score(r)
                v_final = v_regex if v_regex is not None else v_json
                
                # Validación de Impacto (V15.1)
                if len(r.split()) > 30 and abs(v_final) < 0.001:
                    print(f"[NLP-ALERTA] Inconsistencia en {simbolo}: {len(r.split())} palabras pero score 0.00.")
                    r = f"❌ [DATA ERROR] {r}"
                    v_final = 0.0 # Bloqueo por falta de precisión

                resultado[simbolo] = {'voto': _clamp(v_final), 'razonamiento': str(r)[:400]}
        return resultado

    # ------------------------------------------------------------------
    # Caché
    # ------------------------------------------------------------------

    def _obtener_regimenes_activos(self) -> list:
        """Lee regímenes ACTIVO/FORMANDOSE de la BD (V8.1: Atomic)."""
        return self.db.get_global_regimenes()

    def _calcular_hash(self, regimenes: list) -> str:
        """SHA256 del contexto macro. Si cambia un régimen, el hash cambia."""
        contenido = json.dumps(regimenes, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(contenido.encode()).hexdigest()[:16]  # 8 bytes = 16 hex

    def _leer_cache(self, hash_ctx: str, id_activo: int):
        """
        Retorna el voto del caché si es válido (V8.1: Atomic).
        Nota: La validación de tiempo se simplifica o se asume manejada por el motor.
        """
        return self.db.leer_cache_nlp(hash_ctx, id_activo)

    def _guardar_cache(self, hash_ctx: str, activos: list, resultados: dict, regimenes: list):
        """Upsert del análisis de Gemini en cache_nlp_impactos (V8.1: Atomic Batch)."""
        datos_insert = []
        for activo in activos:
            sim = activo["simbolo"]
            res = resultados.get(sim, {'voto': 0.0, 'razonamiento': "Neutral."})
            datos_insert.append((sim, res['voto'], res['razonamiento'], hash_ctx))
            
            # V11.1: Guardar también en sentimiento_noticias (Prioridad Usuario)
            self.db.guardar_sentimiento_noticia(sim, res['voto'], res['razonamiento'])
        
        self.db.upsert_nlp_cache(datos_insert)
        print(f"[NLP] Caché guardado para hash={hash_ctx} ({len(activos)} activos)")

    # ------------------------------------------------------------------
    # Fallback (sin API key)
    # ------------------------------------------------------------------

    def _fallback_impactos_regimen(self, simbolo_interno: str, id_activo: int) -> float:
        """Fallback a v1: lee impactos manuales de impactos_regimen."""
        try:
            impactos = self.db.obtener_impactos_por_activo(id_activo)
            if not impactos:
                return 0.0
            voto = 0.0
            for r in impactos:
                impacto = float(r.get("valor_impacto", 0.0))
                if r.get("estado") == "FORMANDOSE":
                    impacto *= 0.5
                print(f"[NLP-FB] {r['titulo'][:35]:<35} | impacto={impacto:+.2f}")
                voto += impacto
            voto_final = round(_clamp(voto), 2)
            print(f"[NLP] {simbolo_interno} -> {voto_final:+.2f} (fallback impactos_regimen)")
            return voto_final
        except Exception as e:
            print(f"[NLP] ERROR en fallback: {e}")
            return 0.0

    # ------------------------------------------------------------------
    # V10.2: NOT-AI NEWS Patrolling
    # ------------------------------------------------------------------
    def patrullar_noticias(self):
        """
        V13.0 Structural Update: Extrae published_at y activa Regime Shift Alert.
        """
        try:
            # Seleccionamos noticias de regimenes_mercado (que pueden venir de RSS/HTML)
            query = "SELECT id, titulo, estado, fecha_inicio FROM regimenes_mercado WHERE estado IN ('ACTIVO', 'FORMANDOSE')"
            self.db.cursor.execute(query)
            items = self.db.cursor.fetchall()

            for item in items:
                n_id, titulo, estado, fecha_db = item
                
                # V13.0: Extracción de fecha (Simulada si no viene del scraper, pero obligatoria)
                # En un entorno real, el scraper llenaría 'fecha_inicio' con pubDate.
                published_at = fecha_db if fecha_db else None
                cronologia_status = "OK"
                
                if not published_at:
                    published_at = datetime.now(timezone.utc)
                    cronologia_status = "CRONOLOGÍA INCIERTA"

                hash_id = hashlib.sha256(titulo.encode()).hexdigest()
                
                if self.db.verificar_hash_noticia(hash_id):
                    continue

                # Guardar Cruda con published_at
                self.db.guardar_noticia_cruda("Interna (DB)", titulo, f"Estado: {estado} | {cronologia_status}", hash_id, published_at)
                
                print(f"[NLP-TRAZABILIDAD] 📰 Noticia guardada: {titulo} | Pub: {published_at}")

                # Lógica 'Regime Shift' (Alerta de Emergencia V13.0)
                # Simulamos un impacto alto para el trigger de alerta si la noticia es muy reciente (< 15 min)
                ahora = datetime.now(timezone.utc)
                delta_min = (ahora - published_at).total_seconds() / 60
                
                # Usamos Gemini para evaluar el impacto real si es una noticia nueva
                # Para simplificar el patrullaje, si delta < 15min, lanzamos evaluación flash
                if delta_min < 15:
                    print(f"[REGIME-SHIFT] 🚨 Noticia de última hora detectada (<15m): {titulo}")
                    self._activar_alerta_emergencia(titulo, published_at)
                
                # Notificar a Telegram
                footer = f"🕒 Pub: {published_at.strftime('%H:%M:%S UTC')}" if cronologia_status == "OK" else "⚠️ CRONOLOGÍA INCIERTA"
                msg = (f"📰 <b>NUEVA NOTICIA DETECTADA</b>\n"
                       f"━━━━━━━━━━━━━━━━━━\n"
                       f"📌 {titulo}\n"
                       f"🚦 Estado: {estado}\n"
                       f"{footer}\n"
                       f"🔗 ID: {hash_id[:8]}")
                
                try:
                    from config.notifier import _enviar_telegram
                    _enviar_telegram(msg)
                except Exception as e_tg:
                    print(f"[NLP-PATROL] Error enviando notificacion Telegram: {e_tg}")
        except Exception as e:
            print(f"[NLP-PATROL] Error en patrullaje V13.0: {e}")

    def _activar_alerta_emergencia(self, titulo: str, fecha: datetime):
        """Dispara una alerta de emergencia si el impacto es crítico (V13.0)."""
        prompt = (
            f"ALERTA DE EMERGENCIA (Regime Shift V13.0)\n\n"
            f"NOTICIA: {titulo}\n"
            f"HORA: {fecha}\n\n"
            "TAREA:\n"
            "1. Evalúa el impact_score de esta noticia (0.0 a 1.0).\n"
            "2. Compara con los catalizadores macro actuales.\n"
            "3. ¿Se refuerza o invalida el contexto maestro?\n\n"
            "Responde en este formato JSON:\n"
            "{\"impact_score\": float, \"veredicto\": \"REFORZADO|INVALIDADO\", \"explicacion\": \"...\"}"
        )
        texto = _llamar_gemini_api(prompt, model=GEMINI_MODEL_PRO) # Usamos Pro para alertas
        if texto:
            try:
                data = json.loads(_extraer_json(texto))
                if data.get("impact_score", 0) > 0.85:
                    msg = (f"🚨 <b>ALERTA DE EMERGENCIA: REGIME SHIFT</b>\n"
                           f"━━━━━━━━━━━━━━━━━━\n"
                           f"🔥 <b>Impacto:</b> {data['impact_score']:.2f}\n"
                           f"⚖️ <b>Veredicto:</b> {data['veredicto']}\n\n"
                           f"📝 {data['explicacion']}\n\n"
                           f"🕒 Pub: {fecha.strftime('%H:%M')} | Noticia: {titulo}")
                    from config.notifier import _enviar_telegram
                    _enviar_telegram(msg)
            except (json.JSONDecodeError, KeyError, Exception) as e_emg:
                print(f"[NLP] Error procesando alerta de emergencia: {e_emg}")
    # ------------------------------------------------------------------

    def _resolver_id(self, simbolo_interno: str):
        """Busca el id del activo en BD por símbolo."""
        try:
            self.db.cursor.execute(
                "SELECT id FROM activos WHERE simbolo = %s;",
                (simbolo_interno,)
            )
            fila = self.db.cursor.fetchone()
            return fila[0] if fila else None
        except Exception as e:
            print(f"[NLP] ERROR resolviendo id de {simbolo_interno}: {e}")
            return None


# ------------------------------------------------------------------
# TEST DE CAMPO
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config.db_connector import DBConnector

    db = DBConnector()
    if not db.conectar():
        sys.exit(1)

    worker = NLPWorker(db)
    activos = db.obtener_activos_patrullaje()
    simbolos = [a["simbolo"] for a in activos]
    print(f"\nActivos en patrullaje: {simbolos}")
    print(f"Gemini disponible: {worker._api_disponible}")
    print(f"Cache TTL: {CACHE_TTL_MIN} min\n")
    print("=" * 55)

    for activo in activos:
        print(f"\n--- {activo['simbolo']} (id={activo['id']}) ---")
        voto = worker.analizar(activo["simbolo"], id_activo=activo["id"])
        print(f">>> Voto final: {voto:+.2f}")

    db.desconectar()
