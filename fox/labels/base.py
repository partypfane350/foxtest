#===========================
# Basis-Label-Daten und Hilfen
#===========================
LEGACY_MAP = {
    "rechner": "mathe",
    "mathfrage": "mathe",
    "stadtfrage": "geo",
    "kontinentfrage": "geo",
    "termine": "termin",
    "zeitfrage": "time",
}

# Für simple Datum-/Zeit-Erkennung
WEEKDAYS = ["montag","dienstag","mittwoch","donnerstag","freitag","samstag","sonntag"]

# CLI-Hilfe/Texte
LABEL_TEXTS = {
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