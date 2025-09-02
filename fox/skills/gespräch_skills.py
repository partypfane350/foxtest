# =============================
# Gesprächs-Skill 
# =============================
from __future__ import annotations
import re
import random
from typing import Optional, Dict

# Die Sub-Klassen orientieren sich an deinen Label-Beispielen:
# - smalltalk:  wie geht's, witz, was machst du, lieblingsessen
# - begrüßung:  hi, hallo, guten morgen/abend/tag, servus, moin, grüezi
# - verabschiedung: tschüss, bis später, auf wiedersehen, ciao, bis bald
# - info: wer bist du, was kannst du (alles)
#
# Siehe deine Trainingssätze in gespräch_labels.py.

# --- Wörterlisten / Muster ---
_GREET_WORDS = (
    "hallo", "hi", "hey", "servus", "moin", "grüezi",
    "guten morgen", "guten abend", "guten tag", "gute nacht"
)
_BYE_WORDS = (
    "tschüss", "tschuess", "ciao", "auf wiedersehen",
    "bis später", "bis spaeter", "bis bald", "mach's gut", "machs gut"
)

# Smalltalk-Trigger (Regex, robust gegen Varianten)
_RE_HOW_ARE_YOU = re.compile(r"\b(wie\s+geht(?:'s| es)?( dir)?|wie\s+läuft'?s|alles\s+gut)\b", re.I)
_RE_JOKE        = re.compile(r"\b(witz|joke)\b", re.I)
_RE_WHAT_DO     = re.compile(r"\b(was\s+machst\s+du\s+so|was\s+machst\s+du)\b", re.I)
_RE_FAVORITE    = re.compile(r"\b(lieblingsessen|lieblings\s*essen)\b", re.I)

# Info-Trigger
_RE_WHO_ARE_YOU = re.compile(r"\b(wer\s+bist\s+du)\b", re.I)
_RE_WHAT_CAN    = re.compile(r"\b(was\s+kannst\s+du(?:\s+alles)?)\b", re.I)


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    t = " " + (text or "").lower().strip() + " "
    return any((" " + p + " ") in t for p in phrases)


def _reply_greeting(t: str) -> str:
    if "guten morgen" in t:   return "Guten Morgen! Wie kann ich dir helfen?"
    if "guten abend" in t:    return "Guten Abend! Was brauchst du?"
    if "guten tag" in t:      return "Guten Tag! Womit kann ich helfen?"
    if "gute nacht" in t:     return "Gute Nacht! Ich bin trotzdem da, falls du noch was brauchst."
    return random.choice([
        "Hi! Wie kann ich dir helfen?",
        "Hey! Was kann ich für dich tun?",
        "Hallo! Sag mir, was du brauchst."
    ])


def _reply_bye() -> str:
    return random.choice([
        "Bis später!",
        "Ciao! Melde dich, wenn du etwas brauchst.",
        "Auf Wiedersehen! Bis bald."
    ])


def _reply_smalltalk(t: str) -> Optional[str]:
    if _RE_HOW_ARE_YOU.search(t):
        return random.choice([
            "Mir geht’s gut, danke! Und dir?",
            "Alles bestens – bereit zu helfen. Wie kann ich dich unterstützen?",
            "Läuft bei mir 😊 Was steht bei dir an?"
        ])
    if _RE_JOKE.search(t):
        jokes = [
            "Warum können Seeräuber schlecht programmieren? – Weil sie C nicht kennen… Arr!",
            "Ich habe einen Witz über UDP… egal, ob er ankommt. 😄",
            "Treffen sich zwei Arrays. Sagt das eine: 'Sort mal deine Gedanken!'"
        ]
        return random.choice(jokes)
    if _RE_WHAT_DO.search(t):
        return "Ich helfe dir mit Zeit, Terminen, Mathe, Geo/Orten, Wetter und kurzem Wissen. Sag einfach, was du brauchst."
    if _RE_FAVORITE.search(t):
        return "Ich esse nicht – aber ich bin Fan von gut strukturiertem Code und klaren Antworten. 😄"
    return None


def _reply_info(t: str) -> Optional[str]:
    if _RE_WHO_ARE_YOU.search(t):
        return "Ich bin Fox, dein Assistent. Frag mich nach Uhrzeit/Datum, Terminen, Mathe, Geo/Orten, Wetter oder kurzem Fakten-Wissen."
    if _RE_WHAT_CAN.search(t):
        return ("Ich kann: Uhrzeit/Datum sagen, einfache Termine speichern, Mathe rechnen, Orte/Geo-Infos auflösen, "
                "Wetter abrufen (mit API-Key), und kurzes Wissen zusammenfassen. Sag einfach, was du willst.")
    return None


def gespraech_skill(text: str, ctx: Dict | None = None) -> str:
    """
    Antwortet gemäß deinen Gesprächs-Labels:
      - begrüßung   → freundliche Begrüßung
      - verabschiedung → Abschiedsfloskel
      - info        → kurze Selbstbeschreibung/Fähigkeiten
      - smalltalk   → 'wie geht's', Witz, 'was machst du so', 'Lieblingsessen'
      - sonst       → neutrale Rückfrage
    """
    t = (text or "").strip().lower()

    # 1) Begrüßung
    if _has_any(t, _GREET_WORDS):
        return _reply_greeting(t)

    # 2) Verabschiedung
    if _has_any(t, _BYE_WORDS):
        return _reply_bye()

    # 3) Info
    info = _reply_info(t)
    if info:
        return info

    # 4) Smalltalk
    small = _reply_smalltalk(t)
    if small:
        return small

    # 5) Default
    return "Alles klar. Erzähl mir einfach, was du brauchst."
