# =========================
# Wissen-Kategorie
# =========================
CLASSES = ["wissen"]

# Sub-Klassen (für dein zweites, hierarchisches Wissen-Modell)
SUB_CLASSES = [
    "geschichte",
    "wissenschaft",
    "sport",
    "technik",
]

# WICHTIG: Für das OBER-Modell labeln wir diese Texte als "wissen",
# damit es nur die Haupt-Kategorie trifft. Das Submodell trennt später fein aus.
TRAIN = {
    "texts": [
        # geschichte (gehen an SUB-Modell, hier aber "wissen"-gelabelt)
        "wer war napoleon",
        "wann war der 2. weltkrieg",
        "was passierte 1989",
        "wer war karl der große",
        # wissenschaft
        "wer hat die relativitätstheorie entwickelt",
        "was ist ein atom",
        "was ist die lichtgeschwindigkeit",
        "was ist ein schwarzes loch",
        "was ist quantenphysik",
        # sport
        "wer hat die wm 2014 gewonnen",
        "wie viele spieler hat ein fußballteam",
        "wer ist der beste fußballspieler",
        "wie hoch ist der basketballkorb",
        "wer hat die olympischen spiele 2021 gewonnen",
        # technik
        "was ist eine cpu",
        "wer hat das internet erfunden",
        "was ist 5g",
        "was ist künstliche intelligenz",
        "wer hat das telefon erfunden",
        "was ist blockchain",
        "was ist bitcoin",
        "was ist maschinelles lernen",
    ],
    "labels": [
        "wissen","wissen","wissen","wissen",
        "wissen","wissen","wissen","wissen","wissen",
        "wissen","wissen","wissen","wissen","wissen",
        "wissen","wissen","wissen","wissen","wissen","wissen","wissen","wissen",
    ],
}
