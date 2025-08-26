from __future__ import annotations

# Klassen/Intents, die dein Intent-Modell kennt
CLASSES = [
    "smalltalk",
    "geo",        # Orte/Länder-Infos
    "mathe",      # Rechnen
    "wetter",     # nur explizit
    "wissen",     # Platzhalter
    "time",       # Zeit/Datum
    "termin",     # kleiner Kalender
]

# Legacy-Labels => Normalisierung auf heutige Klassen
LEGACY_MAP = {
    "rechner": "mathe",
    "mathfrage": "mathe",
    "stadtfrage": "geo",
    "kontinentfrage": "geo",
    "termine": "termin",
    "zeitfrage": "time",
}

# Für einfache Datums-/Zeit-Erkennung
WEEKDAYS = ["montag","dienstag","mittwoch","donnerstag","freitag","samstag","sonntag"]

# Start-Trainingsdaten – basales Bootstrap für das Intent-Modell
BASE_TRAIN = {
    "texts": [
        "Wie geht es dir?", "Erzähl mir einen Witz", "Hallo Fox", "Was kannst du alles?",
        "Was ist 2 + 2?", "Was ist 3 * 5?", "Was ist 10 - 4?", "Was ist 8 / 2?",
        "Welche Städte gibt es in Deutschland?", "Liste alle Städte in Japan",
        "Welche Kontinente gibt es?", "Nenne mir alle Kontinente",
        "Wie spät ist es?", "Sag mir die Uhrzeit",
        "Wie ist das Wetter heute?", "Wie wird das Wetter morgen?",
        "Wer hat die Relativitätstheorie entwickelt?", "Was ist die größte Stadt der Welt?",
        "Wann ist Weihnachten?", "Wann ist dein Geburtstag?"
    ],
    "labels": [
        "smalltalk","smalltalk","smalltalk","smalltalk",
        "mathe","mathe","mathe","mathe",
        "geo","geo",
        "geo","geo",
        "time","time",
        "wetter","wetter",
        "wissen","wissen",
        "termin","termin"
    ]
}

# Optionale UI-Texte/Labels – zentral, falls du später Mehrsprachigkeit willst
LABEL_TEXTS = {
    "menu": {
        "main": "Hauptmenü",
        "settings": "Einstellungen",
        "exit": "Beenden"
    },
    "responses": {
        "greeting": "Hallo! Wie kann ich dir helfen?",
        "farewell": "Bis bald!"
    },
    "cli": {
        "help": (
            "Befehle:\n"
            "  learn: <frage> => <label>\n"
            "  fact: <key> = <val>\n"
            "  termin: <beschreibung>\n"
            "  audio an | audio aus | save | reload | showmem | showtrain | classes | labelspath | quit\n"
        )
    }
}
