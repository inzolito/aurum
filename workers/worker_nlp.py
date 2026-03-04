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
GEMINI_MODEL     = "gemini-1.5-flash"


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
            print("[NLP] ADVERTENCIA: GEMINI_API_KEY no configurada. "
                  "Usando fallback de impactos_regimen.")

    # ------------------------------------------------------------------
    # API Pública (misma firma que v1)
    # ------------------------------------------------------------------

    def analizar(self, simbolo_interno: str, id_activo: int = None) -> float:
        """
        Retorna el voto macro para el activo dado.
        Usa Gemini con caché inteligente. Fallback a 0.0 si no hay API key.
        """
        if id_activo is None:
            id_activo = self._resolver_id(simbolo_interno)
            if id_activo is None:
                print(f"[NLP] ERROR: '{simbolo_interno}' no encontrado en BD. Voto neutral.")
                return 0.0

        if not self._api_disponible:
            return self._fallback_impactos_regimen(simbolo_interno, id_activo)

        # Obtener contexto macro y su hash
        regimenes  = self._obtener_regimenes_activos()
        hash_ctx   = self._calcular_hash(regimenes)

        # Intentar leer del caché primero
        voto_cache = self._leer_cache(hash_ctx, id_activo)
        if voto_cache is not None:
            print(f"[NLP] {simbolo_interno} (id={id_activo}) -> cache: {voto_cache:+.2f}")
            return voto_cache

        # Caché inválido: llamar a Gemini para TODOS los activos a la vez
        activos_db = self.db.obtener_activos_patrullaje()
        resultados = self._llamar_gemini(regimenes, activos_db)

        if resultados:
            self._guardar_cache(hash_ctx, activos_db, resultados, regimenes)

        voto = resultados.get(simbolo_interno, 0.0)
        print(f"[NLP] {simbolo_interno} (id={id_activo}) -> Gemini: {voto:+.2f}")
        return voto

    # ------------------------------------------------------------------
    # Gemini
    # ------------------------------------------------------------------

    def _llamar_gemini(self, regimenes: list, activos: list) -> dict:
        """
        Llama a Gemini con un prompt multi-activo.
        Retorna dict {simbolo: float} con guardrails aplicados.
        En caso de cualquier error, retorna dict con 0.0 para todos.
        """
        simbolos = [a["simbolo"] for a in activos]
        fallback  = {s: 0.0 for s in simbolos}

        if not regimenes:
            print("[NLP] Sin regímenes activos. Retornando neutrales.")
            return fallback

        # Construir contexto legible para el prompt
        ctx_lineas = []
        for r in regimenes:
            ctx_lineas.append(
                f"- {r['titulo']} ({r['clasificacion']}, estado: {r['estado']})"
            )
        contexto_str = "\n".join(ctx_lineas)
        activos_str  = ", ".join(simbolos)
        json_vacio   = json.dumps({s: 0.0 for s in simbolos})

        prompt = (
            "Actúa como un analista macro senior de mercados financieros. "
            "Analiza el siguiente contexto macroeconómico actual:\n\n"
            f"{contexto_str}\n\n"
            "Devuelve ÚNICAMENTE un JSON válido (sin markdown, sin texto adicional) "
            "con el impacto estimado de -1.0 (muy bajista) a 1.0 (muy alcista) "
            f"para cada uno de estos activos: {activos_str}\n\n"
            f"Formato requerido: {json_vacio}\n\n"
            "Considera correlaciones entre activos (ej: tensiones geopolíticas "
            "suben Oro y Petróleo, bajan S&P500; recorte de tasas FED sube acciones "
            "y debilita USD). Sé preciso y coherente entre activos."
        )

        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            modelo   = genai.GenerativeModel(GEMINI_MODEL)
            respuesta = modelo.generate_content(prompt)
            texto    = respuesta.text.strip()
            print(f"[NLP] Gemini respondio ({len(texto)} chars)")

            # Parsear JSON con guardrails
            return self._parsear_respuesta(texto, simbolos)

        except Exception as e:
            print(f"[NLP] ERROR llamando a Gemini: {e}. Retornando neutrales.")
            return fallback

    def _parsear_respuesta(self, texto: str, simbolos: list) -> dict:
        """
        Guardrail estricto: parsea el JSON de Gemini.
        Cualquier error retorna 0.0 para el activo afectado (no falla el sistema).
        """
        resultado = {s: 0.0 for s in simbolos}
        try:
            json_str = _extraer_json(texto)
            data     = json.loads(json_str)
            for simbolo in simbolos:
                if simbolo in data:
                    resultado[simbolo] = _clamp(data[simbolo])
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[NLP] GUARDRAIL: JSON inválido de Gemini ({e}). Retornando neutrales.")
        return resultado

    # ------------------------------------------------------------------
    # Caché
    # ------------------------------------------------------------------

    def _obtener_regimenes_activos(self) -> list:
        """Lee regímenes ACTIVO/FORMANDOSE de la BD."""
        try:
            self.db.cursor.execute(
                """
                SELECT titulo, clasificacion, estado
                FROM regimenes_mercado
                WHERE estado IN ('ACTIVO', 'FORMANDOSE')
                ORDER BY id;
                """
            )
            cols = ["titulo", "clasificacion", "estado"]
            return [dict(zip(cols, row)) for row in self.db.cursor.fetchall()]
        except Exception as e:
            print(f"[NLP] ERROR leyendo regímenes: {e}")
            return []

    def _calcular_hash(self, regimenes: list) -> str:
        """SHA256 del contexto macro. Si cambia un régimen, el hash cambia."""
        contenido = json.dumps(regimenes, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(contenido.encode()).hexdigest()[:16]  # 8 bytes = 16 hex

    def _leer_cache(self, hash_ctx: str, id_activo: int):
        """
        Retorna el voto del caché si es válido (mismo hash + < TTL minutos).
        Retorna None si el caché no existe o expiró.
        """
        try:
            self.db.cursor.execute(
                """
                SELECT voto, creado_en
                FROM cache_nlp_impactos
                WHERE hash_regimenes = %s AND id_activo = %s
                ORDER BY creado_en DESC
                LIMIT 1;
                """,
                (hash_ctx, id_activo)
            )
            fila = self.db.cursor.fetchone()
            if fila:
                voto, creado_en = fila
                edad = datetime.now(timezone.utc) - creado_en
                if edad < timedelta(minutes=CACHE_TTL_MIN):
                    return float(voto)
                print(f"[NLP] Caché expirado (edad: {int(edad.total_seconds()//60)}min). Reconsultando Gemini.")
        except Exception as e:
            print(f"[NLP] ERROR leyendo caché: {e}")
        return None

    def _guardar_cache(self, hash_ctx: str, activos: list, resultados: dict, regimenes: list):
        """Upsert del análisis de Gemini en cache_nlp_impactos."""
        razonamiento = f"Gemini {GEMINI_MODEL} | Regímenes: {len(regimenes)} activos | " \
                       f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        try:
            for activo in activos:
                sim = activo["simbolo"]
                voto = resultados.get(sim, 0.0)
                self.db.cursor.execute(
                    """
                    INSERT INTO cache_nlp_impactos
                        (hash_regimenes, id_activo, simbolo, voto, razonamiento)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (hash_regimenes, id_activo) DO UPDATE
                        SET voto         = EXCLUDED.voto,
                            razonamiento = EXCLUDED.razonamiento,
                            creado_en    = CURRENT_TIMESTAMP;
                    """,
                    (hash_ctx, activo["id"], sim, voto, razonamiento)
                )
            self.db.conn.commit()
            print(f"[NLP] Caché guardado para hash={hash_ctx} ({len(activos)} activos)")
        except Exception as e:
            print(f"[NLP] ERROR guardando caché: {e}")

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
    # Helpers
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
