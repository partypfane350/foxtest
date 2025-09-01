#===========================
# Label-Module (Ober-Modell)
#===========================
from . import base, geo_labels, gespräch_labels, mathe_labels, termin_labels, time_labels, wetter_labels, wissen_labels

# ===== Hauptklassen =====
CLASSES = []
for mod in (gespräch_labels, geo_labels, mathe_labels, wetter_labels, wissen_labels, time_labels, termin_labels):
    CLASSES.extend(getattr(mod, "CLASSES", []))



# ===== Sub-Klassen (hierarchisch) =====
SUB_CLASSES = {}
for mod in (wissen_labels,):
    if hasattr(mod, "SUB_CLASSES") and getattr(mod, "CLASSES", []):
        parent = mod.CLASSES[0]
        SUB_CLASSES[parent] = mod.SUB_CLASSES

for mod in (gespräch_labels,):
    if hasattr(mod, "SUB_CLASSES") and getattr(mod, "CLASSES", []):
        parent = mod.CLASSES[0]
        SUB_CLASSES[parent] = mod.SUB_CLASSES

# ===== Bootstrap-Training für das Ober-Modell (nur Hauptlabels!) =====
BASE_TRAIN = {"texts": [], "labels": []}
for mod in (gespräch_labels, geo_labels, mathe_labels, wetter_labels, wissen_labels, time_labels, termin_labels):
    tr = getattr(mod, "TRAIN", None)
    if tr:
        BASE_TRAIN["texts"].extend(tr.get("texts", []))
        BASE_TRAIN["labels"].extend(tr.get("labels", []))

# ===== Legacy/Weekdays/CLI-Texte =====
LEGACY_MAP = base.LEGACY_MAP
WEEKDAYS   = base.WEEKDAYS
LABEL_TEXTS = base.LABEL_TEXTS