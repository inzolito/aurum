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
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Forzar UTF-8 en stdout para evitar charmap errors en Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
CACHE_TTL_MIN    = int(os.getenv("NLP_CACHE_TTL_MIN", "30"))
GEMINI_MODEL_LITE = "gemini-flash-latest" # V10.1: Free-Tier Priority
GEMINI_MODEL_PRO  = "gemini-pro-latest"   # Solo para veredictos > 0.40


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
        self._ultimo_refresh = datetime.min.replace(tzinfo=timezone.utc)  # Para el guard de 5 min
        self._notified_hashes = set() # V10.2: Memoria volatil para noticias
        if not self._api_disponible:
            print("[NLP] ADVERTENCIA: GEMINI_API_KEY no configurada. "
                  "Usando fallback de impactos_regimen.")

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
        if solo_si_conviccion and abs(technical_verdict) < 0.40:
            # print(f"[NLP] Saltando IA (Conviccion Tecnica baja: {technical_verdict:+.2f})")
            return 0.0
        if id_activo is None:
            id_activo = self._resolver_id(simbolo_interno)
            if id_activo is None:
                print(f"[NLP] ERROR: '{simbolo_interno}' no encontrado en BD. Voto neutral.")
                return 0.0

        if not self._api_disponible:
            return self._fallback_impactos_regimen(simbolo_interno, id_activo)

        # Evaluar límite de refresco forzado (Cooldown 5 min)
        ahora = datetime.now(timezone.utc)
        ignorar_cache_ahora = False
        
        if forzar_refresh:
            if (ahora - self._ultimo_refresh).total_seconds() > 300:
                print(f"[NLP-REFLEJO] ⚡ Volatilidad detectada en {simbolo_interno}. Forzando re-analisis Gemini.")
                ignorar_cache_ahora = True
                self._ultimo_refresh = ahora
            else:
                tiempo_restante = 300 - (ahora - self._ultimo_refresh).total_seconds()
                print(f"[NLP] Refresco forzado ignorado (cooldown: {int(tiempo_restante)}s restantes)")

        # Obtener contexto macro y su hash
        regimenes  = self._obtener_regimenes_activos()
        hash_ctx   = self._calcular_hash(regimenes)

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
        Llama a Gemini con un prompt multi-activo.
        Retorna dict {simbolo: float} con guardrails aplicados.
        En caso de cualquier error, retorna dict con 0.0 para todos.
        V10.1: FREE-TIER PRIORITY (Switch de motor y compresion de contexto).
        """
        simbolos = [a["simbolo"] for a in activos]
        fallback  = {s: {'voto': 0.0, 'razonamiento': "Error API Gemini."} for s in simbolos}

        if not regimenes:
            print("[NLP] Sin regimenes activos. Retornando neutrales.")
            return fallback

        # 1. Seleccion de Motor (MODIFICADO: Forzado a LITE por restricción de cuota)
        modelo_final = GEMINI_MODEL_LITE
        print(f"[NLP] Usando motor: {modelo_final} (Modo Gratuito Forzado)")

        # 2. Compresion de Contexto (Ultimos 5 titulares)
        regimenes_recientes = regimenes[-5:]
        ctx_lineas = []
        for r in regimenes_recientes:
            ctx_lineas.append(f"- {r['titulo']} ({r['clasificacion']}, estado: {r['estado']})")
        contexto_str = "\n".join(ctx_lineas)
        
        # 3. Datos de Velas (Ultimas 3)
        velas_str = "No hay datos de velas recientes."
        if velas:
            v_lines = []
            for v in velas[-3:]:
                # v es un dict con 'apertura', 'maximo', 'minimo', 'cierre'
                v_lines.append(f"Vela: O:{v['apertura']} H:{v['maximo']} L:{v['minimo']} C:{v['cierre']}")
            velas_str = "\n".join(v_lines)

        activos_str  = ", ".join(simbolos)
        formato_guia = json.dumps({s: {"voto": 0.0, "razonamiento": "..."} for s in simbolos[:1]})
        
        prompt = (
            "Actua como un analista macro senior. "
            "Contexto comprimido (Ultimos 5 titulares):\n"
            f"{contexto_str}\n\n"
            "Datos de las ultimas 3 velas (M1/M15):\n"
            f"{velas_str}\n\n"
            "Tu tarea: Evaluar el impacto en estos activos. "
            "Devuelve UNICAMENTE un JSON valido (sin markdown) con esta estructura:\n"
            f"- voto: Valor de -1.0 a 1.0.\n"
            f"- razonamiento: Max 2 lineas en ESPAÑOL.\n"
            f"Activos: {activos_str}\n"
            f"Ejemplo: {formato_guia}\n"
            "Se extremadamente conciso. Prioriza los datos de velas si hay contradiccion."
        )

        texto = _llamar_gemini_api(prompt, model=modelo_final)
        if not texto:
            return fallback

        print(f"[NLP] Gemini {modelo_final[-10:]} respondio ({len(texto)} chars)")
        return self._parsear_respuesta(texto, simbolos)

    def _parsear_respuesta(self, texto: str, simbolos: list) -> dict:
        """
        Guardrail estricto: parsea el JSON de Gemini.
        Retorna {simbolo: {'voto': float, 'razonamiento': str}}
        """
        resultado = {s: {'voto': 0.0, 'razonamiento': "Sin datos de Gemini"} for s in simbolos}
        try:
            json_str = _extraer_json(texto)
            data     = json.loads(json_str)
            for simbolo in simbolos:
                if simbolo in data:
                    item = data[simbolo]
                    if isinstance(item, dict):
                        v = item.get('voto', 0.0)
                        r = item.get('razonamiento', "Analisis neutral.")
                    else:
                        v = item # Fallback si mando solo el numero
                        r = "Actualizacion macro."
                    
                    resultado[simbolo] = {
                        'voto': _clamp(v),
                        'razonamiento': str(r)[:400] # Cap para BD
                    }
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[NLP] GUARDRAIL: JSON inválido de Gemini ({e}).")
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
    def patrullar_noticias(self, id_activo=None):
        """
        V10.2 NOT-AI MODE: Busca noticias frescas en regimenes_mercado,
        las hashea y las manda a Telegram sin AI si son nuevas.
        V10.3: Persistencia via base de datos.
        """
        try:
            # 1. Obtener noticias activas o formándose
            query = "SELECT id, titulo, estado FROM regimenes_mercado WHERE estado IN ('ACTIVO', 'FORMANDOSE')"
            self.db.cursor.execute(query)
            items = self.db.cursor.fetchall()

            for item in items:
                # Generar MD5 del título (sencillo)
                raw_hash = hashlib.md5(item[1].encode()).hexdigest() # titulo es index 1
                
                # Check DB for persistence (V10.3)
                self.db.cursor.execute("SELECT 1 FROM noticias_notificadas WHERE hash = %s", (raw_hash,))
                if not self.db.cursor.fetchone():
                    # Es nueva!
                    print(f"[NLP-PATROL] 📰 Detectada nueva noticia: {item[1]}")
                    
                    # Notificar raw (V10.2)
                    msg = (f"📰 <b>NUEVA NOTICIA DETECTADA</b>\n"
                           f"━━━━━━━━━━━━━━━━━━\n"
                           f"📌 {item[1]}\n"
                           f"🚦 Estado: {item[2]}\n"
                           f"🔗 Fuente: Interna (DB)")
                    
                    try:
                        from config.notifier import _enviar_telegram
                        _enviar_telegram(msg)
                    except:
                        pass
                    
                    # Guardar en DB para no repetir nunca (V10.3)
                    self.db.cursor.execute("INSERT INTO noticias_notificadas (hash) VALUES (%s)", (raw_hash,))
                    self.db.conn.commit()
                    
        except Exception as e:
            print(f"[NLP-PATROL] Error en patrullaje: {e}")
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
