# ===========================
# Skill-Module (relative imports)
# ===========================

# Geo
from .geo_skills import geo_skill, resolve_place, search_places

# Wetter
from .weather_skills import get_weather

# Zeit/Datum
from .time_skills import time_skill

# Mathe
from .mathe_skills import mathe_skill, try_auto_calc

# Knowledge-DB (+ Training)
from .knowledge import (
    init_db as init_knowledge_db,
    set_fact,
    get_fact,
    search_facts,
    add_training_pair,
    list_training,
)

# Gespräch & Termin
from .gespräch_skills import gespraech_skill
from .termin_skills import termin_skill

__all__ = [
    "geo_skill", "resolve_place", "search_places",
    "get_weather",
    "time_skill",
    "mathe_skill", "try_auto_calc",
    "init_knowledge_db", "set_fact", "get_fact", "search_facts",
    "add_training_pair", "list_training",
    "gespraech_skill", "termin_skill",
]
