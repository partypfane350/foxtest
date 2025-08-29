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
        # wissenschaft
        "wer hat die relativitätstheorie entwickelt",
        "was ist ein atom",
        # sport
        "wer hat die wm 2014 gewonnen",
        "wie viele spieler hat ein fußballteam",
        # technik
        "was ist eine cpu",
        "wer hat das internet erfunden",
    ],
    "labels": [
        "wissen","wissen",
        "wissen","wissen",
        "wissen","wissen",
        "wissen","wissen",
    ],
}
