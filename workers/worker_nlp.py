class NLPWorker:
    """
    Obrero de Contexto Macroeconómico — VERSION AGNOSTICA AL ACTIVO.
    Fuente de verdad: tabla impactos_regimen (Many-to-Many con regimenes_mercado).
    Ya no usa columnas hardcodeadas (impacto_base_oro, etc.).
    El impacto de cada régimen se define por fila en la BD para cada activo específico.
    Devuelve un voto entre -1.0 y +1.0.
    """

    def __init__(self, db):
        self.db = db

    def analizar(self, simbolo_interno: str, id_activo: int = None) -> float:
        """
        Calcula el voto macro para el activo.
        Si id_activo no se pasa, lo busca en la BD por simbolo_interno.
        """
        # 1. Resolver id_activo si no viene dado
        if id_activo is None:
            id_activo = self._resolver_id(simbolo_interno)
            if id_activo is None:
                print(f"[NLP] ERROR: activo '{simbolo_interno}' no encontrado en BD. Voto neutral.")
                return 0.0

        # 2. Obtener impactos desde la nueva tabla agnóstica
        impactos = self.db.obtener_impactos_por_activo(id_activo)

        if not impactos:
            print(f"[NLP] Sin impactos registrados para {simbolo_interno} (id={id_activo}). Voto neutral.")
            return 0.0

        voto_acumulado = 0.0

        # 3. Suma vectorial
        for r in impactos:
            impacto = float(r.get("valor_impacto", 0.0))

            # Régimen en formación = solo el 50% de su fuerza
            if r.get("estado") == "FORMANDOSE":
                impacto *= 0.5

            print(f"[NLP]   {r['titulo'][:40]:<40} | {r['clasificacion']:<20} | "
                  f"estado={r['estado']:<12} | impacto={impacto:+.2f}")
            voto_acumulado += impacto

        voto_final = round(max(-1.0, min(1.0, voto_acumulado)), 2)
        print(f"[NLP] {simbolo_interno} (id={id_activo}) -> Suma: {voto_acumulado:+.3f} | Voto: {voto_final:+.2f}")
        return voto_final

    def _resolver_id(self, simbolo_interno: str) -> int | None:
        """Busca el id del activo en la BD por símbolo interno."""
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
    if db.conectar():
        worker = NLPWorker(db)

        # Obtener todos los activos dinámicamente
        activos = db.obtener_activos_patrullaje()
        print(f"\nActivos en patrullaje: {[a['simbolo'] for a in activos]}\n")

        print("=" * 55)
        print("  NLPWorker Agnostico — Test de Campo")
        print("=" * 55)

        for activo in activos:
            print(f"\n--- {activo['simbolo']} (id={activo['id']}) ---")
            voto = worker.analizar(activo["simbolo"], id_activo=activo["id"])
            print(f">>> Voto final: {voto:+.2f}")

        db.desconectar()
