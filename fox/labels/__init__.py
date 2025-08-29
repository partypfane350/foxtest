#===========================
# Label-Module (Ober-Modell)
#===========================
from . import base, smalltalk, geo, mathe, wetter, wissen, time, termin

# ===== Hauptklassen =====
CLASSES = []
for mod in (smalltalk, geo, mathe, wetter, wissen, time, termin):
    CLASSES.extend(getattr(mod, "CLASSES", []))

# ===== Sub-Klassen (hierarchisch) – z. B. für wissen =====
SUB_CLASSES = {}
for mod in (wissen,):
    if hasattr(mod, "SUB_CLASSES") and getattr(mod, "CLASSES", []):
        parent = mod.CLASSES[0]
        SUB_CLASSES[parent] = mod.SUB_CLASSES

# ===== Bootstrap-Training für das Ober-Modell (nur Hauptlabels!) =====
BASE_TRAIN = {"texts": [], "labels": []}
for mod in (smalltalk, geo, mathe, wetter, wissen, time, termin):
    tr = getattr(mod, "TRAIN", None)
    if tr:
        BASE_TRAIN["texts"].extend(tr.get("texts", []))
        BASE_TRAIN["labels"].extend(tr.get("labels", []))

# ===== Legacy/Weekdays/CLI-Texte =====
LEGACY_MAP = base.LEGACY_MAP
WEEKDAYS   = base.WEEKDAYS
LABEL_TEXTS = base.LABEL_TEXTS