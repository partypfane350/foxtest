from pathlib import Path

# --- Metadaten & Pfade ---
__version__ = "0.1.0"
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent  # Ordner über 'fox'

# Öffentliches API (macht Autocompletion angenehmer)
__all__ = [
    # Labels / Konstanten
    "CLASSES", "LABEL_TEXTS", "LEGACY_MAP", "WEEKDAYS",
    # Speech
    "Speech", "SpeechIn",
    # Geo
    "geo_skill", "resolve_place", "search_places",
    # Wetter
    "get_weather",
    # Zeit
    "time_skill",
    # Mathe
    "mathe_skill", "try_auto_calc",
    # Knowledge-DB
    "init_knowledge_db", "set_fact", "get_fact", "search_facts",
    # Pfade & Version
    "PACKAGE_ROOT", "PROJECT_ROOT", "__version__",
]

# --- Re-Exports (leichte Importe innerhalb des Pakets) ---
from .labels import CLASSES, LABEL_TEXTS, LEGACY_MAP, WEEKDAYS
from .speech_out import Speech
from .speech_in import SpeechIn
from .geo import geo_skill, resolve_place, search_places
from .weather import get_weather
from .time import time_skill
from .mathe import mathe_skill, try_auto_calc
from .knowledge import init_db as init_knowledge_db, set_fact, get_fact, search_facts