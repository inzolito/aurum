"""
Configuración centralizada de logging para Aurum.
Todos los módulos deben obtener su logger así:

    import logging
    logger = logging.getLogger("aurum.<modulo>")

Jerarquía de loggers:
    aurum                → root del proyecto
    aurum.main           → motor principal
    aurum.manager        → gerente ensemble
    aurum.db             → conector de base de datos
    aurum.heartbeat      → watchdog SHIELD
    aurum.trend          → TrendWorker
    aurum.nlp            → NLPWorker
    aurum.flow           → FlowWorker
    aurum.hurst          → HurstWorker
    aurum.volume         → VolumeWorker
    aurum.cross          → CrossWorker
    aurum.spread         → SpreadWorker
    aurum.vix            → VIXWorker
    aurum.structure      → StructureWorker (Sniper)
    aurum.hunter         → NewsHunter
"""

import logging
import logging.handlers
import os
from pathlib import Path

# Directorio de logs (se crea si no existe)
_LOG_DIR  = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "aurum.log"

# Formato unificado
_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)-20s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """
    Configura el logging global de Aurum.
    Llamar UNA sola vez al inicio de main.py / heartbeat.py.

    Args:
        level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
    """
    _LOG_DIR.mkdir(exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Handler: consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    # Handler: archivo rotativo (10 MB max, 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # El archivo siempre guarda todo
    file_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    # Root logger de Aurum
    aurum_logger = logging.getLogger("aurum")
    aurum_logger.setLevel(logging.DEBUG)
    aurum_logger.handlers.clear()
    aurum_logger.addHandler(console_handler)
    aurum_logger.addHandler(file_handler)
    aurum_logger.propagate = False  # No escalar al root logger de Python

    aurum_logger.info("Logging inicializado — nivel=%s | archivo=%s", level, _LOG_FILE)


def get_logger(name: str) -> logging.Logger:
    """
    Retorna un logger con el prefijo 'aurum.' para el módulo dado.
    Ejemplo: get_logger("manager") → logging.getLogger("aurum.manager")
    """
    return logging.getLogger(f"aurum.{name}")
