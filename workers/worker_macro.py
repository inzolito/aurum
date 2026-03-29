"""
MacroWorker — V18.1
Worker pasivo de contexto macro estructural.

Lee los regimenes_macro activos desde BD (via cache) y devuelve un voto
persistente en [-1.0, +1.0] para cada activo, basado en la direccion
e intensidad de los regimenes que lo afectan.

A diferencia de todos los demas workers:
- NO llama APIs externas (cero latencia adicional)
- Vota TODOS los ciclos, haya o no noticias nuevas
- Su opinion persiste durante semanas o meses (bear market, guerras, ciclos macro)

Complementa al NLPWorker: el NLP captura el impacto de noticias puntuales,
el MacroWorker captura el regimen estructural persistente.
"""

import json


class MacroWorker:
    """
    Vota sobre un activo basandose en los regimenes macro activos.

    No requiere db ni mt5 en el constructor — los regimenes se pasan
    como argumento en cada llamada a votar() para evitar queries
    redundantes (el Manager ya los carga una vez por ciclo).
    """

    def votar(self, simbolo: str, regimenes: list) -> float:
        """
        Calcula el voto macro para un activo dado los regimenes activos.

        Args:
            simbolo:   Simbolo del activo, ej: 'BTCUSD', 'XAUUSD'
            regimenes: Lista de dicts con campos:
                       direccion, peso, activos_afectados (JSON string o None)

        Returns:
            float en [-1.0, +1.0]
            +1.0 = contexto macro plenamente alcista para este activo
            -1.0 = contexto macro plenamente bajista para este activo
             0.0 = contexto neutro o sin regimenes relevantes
        """
        if not regimenes:
            return 0.0

        contribuciones = []

        for r in regimenes:
            peso = float(r.get("peso", 0.5))
            if peso <= 0:
                continue

            activos_json = r.get("activos_afectados")
            contribucion = None

            if activos_json:
                # Regimen con activos especificos — buscar este simbolo
                try:
                    activos_lista = json.loads(activos_json)
                    match = next(
                        (a for a in activos_lista if a.get("simbolo") == simbolo),
                        None
                    )
                    if match:
                        dir_activo = match.get("dir", "").upper()
                        if dir_activo == "UP":
                            contribucion = peso
                        elif dir_activo == "DOWN":
                            contribucion = -peso
                        # Si dir es NEUTRAL o desconocido, no contribuye
                    else:
                        # Simbolo no listado explicitamente en el regimen.
                        # Fallback: aplicar la direccion global del regimen al 40% del peso.
                        # Garantiza que ningun activo quede con voto macro=0 cuando hay
                        # regimenes activos (ej: indices en regimenes geopoliticos/monetarios).
                        direccion_global = r.get("direccion", "").upper()
                        if direccion_global == "RISK_ON":
                            contribucion = peso * 0.4
                        elif direccion_global == "RISK_OFF":
                            contribucion = -peso * 0.4
                        # VOLATIL sin match especifico → neutro (0.0), sin contribucion
                except (json.JSONDecodeError, TypeError):
                    pass
            else:
                # Regimen global (activos_afectados = NULL) — aplica a todos
                direccion = r.get("direccion", "").upper()
                if direccion == "RISK_ON":
                    contribucion = peso
                elif direccion == "RISK_OFF":
                    contribucion = -peso
                elif direccion == "VOLATIL":
                    contribucion = 0.0  # volatilidad sin direccion = neutro

            if contribucion is not None:
                contribuciones.append(contribucion)

        if not contribuciones:
            return 0.0

        voto = sum(contribuciones) / len(contribuciones)
        return round(max(-1.0, min(1.0, voto)), 4)
