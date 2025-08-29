#===========================
# Label-Daten für "Smalltalk"
#===========================
CLASSES = ["gespräch"]

SUB_CLASSES = [
    "smalltalk",
    "begrüßung",
    "verabschiedung",
    "info",
]

TRAIN = {
    "texts": [
        # smalltalk
        "Wie geht es dir?",
        "Was machst du so?",
        "Erzähl mir einen Witz",
        "Was ist dein Lieblingsessen?",
        #begrüßung
        "Guten Morgen",
        "Hi",        
        "Hallo Fox",
        #verabschiedung
        "Tschüss",
        "Bis später",
        "Auf Wiedersehen",
        #info
        "Wer bist du?",
        "Was kannst du?",
        "Was kannst du alles?",
    ],
    "labels": [ 
        "gespräch","gespräch","gespräch","gespräch",
        "gespräch","gespräch","gespräch",
        "gespräch","gespräch","gespräch",
        "gespräch","gespräch","gespräch",
    ],
}