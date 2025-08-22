
from __future__ import annotations

import os
import re
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from collections import deque
from typing import Dict, Any, List, Optional

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

# === Skills/Module ===
from fox.geo import geo_skill                 
from fox.weather import get_weather            
from fox.mathe import try_auto_calc, mathe_skill as mathe_skill_lib
from fox.time import time_skill               

# ==== sprach Ein-/Ausgabe ====
from fox.speech_in import SpeechIn as VoskSpeechIn       
from fox.speech_out import Speech     

# =========================
# Konfiguration & Konstanten
# =========================

MODEL_PATH       = Path("fox_intent.pkl")
TRAIN_PATH       = Path("train_data.json")
FACTS_PATH       = Path("facts.json")
CALENDAR_PATH    = Path("calendar.json")

CONF_THRESHOLD   = 0.60   # Mindest-Konfidenz fürs Modell-Routing
MEMORY_SIZE      = 200    # Verlaufsspeicher (leichtgewichtig)
RANDOM_STATE     = 42     # Reproduzierbarkeit
SGD_MAX_ITER     = 1000
SGD_TOL          = 1e-3

CLASSES = [
    "smalltalk",
    "geo",        # Orte/Länder-Infos
    "mathe",      # Rechnen
    "wetter",     # nur explizit
    "wissen",     # Platzhalter
    "time",       # Zeit/Datum
    "termin",     # kleiner Kalender
]
# wissen bearbeiten 

LEGACY_MAP = {
    "rechner": "mathe",
    "mathfrage": "mathe",
    "stadtfrage": "geo",
    "kontinentfrage": "geo",
    "termine": "termin",
    "zeitfrage": "time",
}

WEEKDAYS = ["montag","dienstag","mittwoch","donnerstag","freitag","samstag","sonntag"]

# Start-Trainingsdaten (klein & zielgerichtet)
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

# ==========
# Utilities
# ==========

def normalize_label(lbl: str) -> str:
    return LEGACY_MAP.get(lbl, lbl)

def load_json(path: Path, default):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_datetime(text: str) -> Dict[str, Optional[str]]:
    t = (text or "").lower()
    when = "heute" if "heute" in t else ("morgen" if "morgen" in t else None)
    if not when:
        for wd in WEEKDAYS:
            if wd in t:
                when = wd
                break
    m = re.search(r"(\d{1,2})[:.](\d{2})", t)
    clock = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}" if m else None
    return {"when": when, "time": clock}

def extract_weather_query(text: str) -> str:
    m = re.search(r"\bin\s+(.+)$", text or "", flags=re.IGNORECASE)
    q = (m.group(1) if m else text or "").strip()
    return q

# ==========
# Logging
# ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("fox")

for name in ("comtypes", "comtypes.client", "comtypes.gen", "pyttsx3"):
    lg = logging.getLogger(name)
    lg.setLevel(logging.WARNING)   
    lg.propagate = False

# ===========================
# ML: Vektorisierer & Klassif.
# ===========================

@dataclass
class IntentModel:
    clf: SGDClassifier
    vectorizer: TfidfVectorizer
    meta: Dict[str, Any]

    @staticmethod
    def fit_from_texts(texts: List[str], labels: List[str]) -> "IntentModel":
        vec = TfidfVectorizer()
        X = vec.fit_transform(texts)
        clf = SGDClassifier(loss="log_loss", max_iter=SGD_MAX_ITER, tol=SGD_TOL, random_state=RANDOM_STATE)
        clf.fit(X, labels)
        return IntentModel(clf=clf, vectorizer=vec, meta={"n_samples": len(texts)})

    def save(self, path: Path) -> None:
        joblib.dump((self.clf, self.vectorizer, self.meta), path)

    @staticmethod
    def load(path: Path) -> "IntentModel":
        data = joblib.load(path)
        if isinstance(data, tuple) and len(data) == 3:
            clf, vec, meta = data
        else:
            # Abwärtskompatibilität
            clf, vec = data
            meta = {}
        return IntentModel(clf=clf, vectorizer=vec, meta=meta)

# ==========================
# Core Assistant Orchestrator
# ==========================

class FoxAssistant:
    def __init__(self):
        self.memory = deque(maxlen=MEMORY_SIZE)  
        # Trainingsdaten laden/mergen
        persisted = load_json(TRAIN_PATH, {"texts": [], "labels": []})
        self.train_texts: List[str] = list(BASE_TRAIN["texts"]) + list(persisted.get("texts", []))
        self.train_labels: List[str] = list(BASE_TRAIN["labels"]) + list(persisted.get("labels", []))
        # Modell bauen/laden
        if MODEL_PATH.exists():
            self.model = IntentModel.load(MODEL_PATH)
            log.info("Modell geladen (%s).", MODEL_PATH)
        else:
            self.model = IntentModel.fit_from_texts(self.train_texts, self.train_labels)
            self.model.save(MODEL_PATH)
            log.info("Modell neu trainiert (%d Samples).", len(self.train_texts))

    # ===== Skills =====

    def smalltalk(self, text: str, ctx: Dict[str, Any]) -> str:
        if "witz" in (text or "").lower():
            return "Treffen sich zwei Bytes. Sagt das eine: 'WLAN hier?' — 'Nee, nur LAN.'"
        return "Alles gut! Was brauchst du?"

    def mathe(self, text: str, ctx: Dict[str, Any]) -> str:
        """Wrapper, damit wir den Namen 'mathe_skill' aus fox.mathe nicht überschreiben."""
        res = try_auto_calc(text)
        if res is not None:
            return f"Ergebnis: {res}"
        return mathe_skill_lib(text, ctx)  
    
    def geo_info(self, text: str, ctx: Dict[str, Any]) -> str:
        return geo_skill(text, ctx)

    def wetter(self, text: str, ctx: Dict[str, Any]) -> str:
        q = extract_weather_query(text)
        if not q:
            return "Sag mir eine Stadt für Wetter (z. B. 'Wetter in Bern')."
        return get_weather(q)

    def wissen(self, text: str, ctx: Dict[str, Any]) -> str:
        return "(Demo) Wissensfrage – später Wikipedia/DB anbinden."

    def termin(self, text: str, ctx: Dict[str, Any]) -> str:
        dt = extract_datetime(text)
        if not dt["when"] and not dt["time"]:
            return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."
        evts = load_json(CALENDAR_PATH, [])
        evts.append({"text": text, "when": dt["when"], "time": dt["time"]})
        save_json(CALENDAR_PATH, evts)
        pieces = [p for p in [dt["when"], dt["time"]] if p]
        return f"Okay, Termin gespeichert: {' '.join(pieces)}".strip()

    def time_now(self, text: str, ctx: Dict[str, Any]) -> str:
        return time_skill(text, ctx)

    def fallback(self, text: str, ctx: Dict[str, Any]) -> str:
        return "Das weiß ich noch nicht. Erklär mir kurz, was du brauchst – dann lerne ich es."

    # ===== Routing =====

    def route(self, label: str, text: str, ctx: Dict[str, Any]) -> str:
        label = normalize_label(label)
        if label == "smalltalk": return self.smalltalk(text, ctx)
        if label == "time":      return self.time_now(text, ctx)
        if label == "geo":       return self.geo_info(text, ctx)
        if label == "wissen":    return self.wissen(text, ctx)
        if label == "wetter":    return self.wetter(text, ctx)
        if label == "mathe":     return self.mathe(text, ctx)
        if label == "termin":    return self.termin(text, ctx)
        return self.fallback(text, ctx)

    # ===== Handle =====

    def handle(self, user: str) -> str:
        # 1) Sofort-Mathe (unabhängig vom Intent)
        auto = try_auto_calc(user)
        if auto is not None:
            reply = f"Das Ergebnis ist {round(auto, 6)}."
            self._memorize(user, reply, via="auto-mathe")
            return reply

        # 2) Intent-Klassifizierung
        X = self.model.vectorizer.transform([user])
        proba = self.model.clf.predict_proba(X)[0]
        idx = int(proba.argmax())
        label = normalize_label(self.model.clf.classes_[idx])
        conf = float(proba[idx])

        slots = extract_datetime(user)

        # Termin braucht Slots
        if label == "termin" and not (slots["when"] or slots["time"]):
            return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."

        # 3) Fallback bei geringer Konfidenz
        if conf < CONF_THRESHOLD:
            reply = self.fallback(user, {"slots": slots, "memory": list(self.memory), "conf": conf})
            self._memorize(user, reply, label=label, conf=conf)
            return reply

        # 4) Normaler Skill-Rückweg
        reply = self.route(label, user, {"slots": slots, "memory": list(self.memory), "conf": conf})
        self._memorize(user, reply, label=label, conf=conf)
        return reply

    def _memorize(self, user: str, reply: str, **meta) -> None:
        self.memory.append({"user": user, "fox": reply, **meta})

    # ===== Training / Persistenz =====

    def fit_fresh(self) -> None:
        self.model = IntentModel.fit_from_texts(self.train_texts, self.train_labels)
        self.model.save(MODEL_PATH)
        log.info("Neu trainiert (%d Samples).", len(self.train_texts))

    def learn_pair(self, question: str, label: str) -> None:
        label = normalize_label(label)
        if label not in CLASSES:
            raise ValueError(f"Unbekanntes Label '{label}'. Erlaubt: {', '.join(CLASSES)}")
        self.train_texts.append(question)
        self.train_labels.append(label)
        save_json(TRAIN_PATH, {"texts": self.train_texts, "labels": self.train_labels})
        self.fit_fresh()

    def save_all(self) -> None:
        self.model.save(MODEL_PATH)
        save_json(TRAIN_PATH, {"texts": self.train_texts, "labels": self.train_labels})
        log.info("Modell & Trainingsdaten gespeichert.")

# =========
# CLI-Loop
# =========

def main():
    print("🦊 Fox Assistant — Befehle:")
    print("  learn: <frage> => <label>")
    print("  fact: <key> = <val>")
    print("  termin: <beschreibung>")
    print("  audio an | audio aus | save | reload | showmem | showtrain | classes | quit\n")

    fox = FoxAssistant()
    speech = Speech(enabled=True)  
    mic = VoskSpeechIn(lang="de")  # oder model_path="models/vosk-model-small-de-0.15"

    while True:
        try:
            user = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCiao!")
            break
        if not user:
            continue

        l = user.lower()

        if l in ("quit", "exit"):
            print("Bis bald!")
            break

        # === Audio-Steuerung (ein/aus) ===
        if l == "audio an":
            speech.set_enabled(True)
            print("Fox: Audio EIN")
            continue
        if l == "audio aus":
            speech.set_enabled(False)
            print("Fox: Audio AUS")
            continue
        # Liste der Geräte anzeigen
        if l in ("mikro geraete", "mikro geräte", "mikro devices"):
            VoskSpeechIn.list_input_devices()
            continue

        # Aufnahme mit Standardgerät
        if l == "mikro":
            heard = mic.listen_once(max_seconds=8)
            if heard:
                print(f"Du (Mikro): {heard}")
                reply = fox.handle(heard)
                print("Fox:", reply); speech.say(reply)
            else:
                msg = "Ich habe nichts verstanden."
                print("Fox:", msg); speech.say(msg)
            continue

        # Gerät wechseln: z. B. "mikro device 2"
        if l.startswith("mikro device "):
            try:
                idx = int(l.split()[-1])
                mic = VoskSpeechIn(lang="de", device=idx)
                print(f"Fox: Mikrofon auf Device {idx} gesetzt.")
            except Exception as e:
                print(f"Fox: Konnte Gerät nicht setzen: {e}")
            continue

        # === Utility-Befehle ===
        if l == "save":
            fox.save_all()
            print(f"Fox: Modell + Trainingsdaten gespeichert → {MODEL_PATH}")
            continue

        if l == "reload":
            fox.model = IntentModel.load(MODEL_PATH)
            print("Fox: Modell neu geladen.")
            continue

        if l == "showmem":
            print(json.dumps(list(fox.memory), ensure_ascii=False, indent=2))
            continue

        if l == "showtrain":
            print(json.dumps({"texts": fox.train_texts, "labels": fox.train_labels}, ensure_ascii=False, indent=2))
            continue

        if l == "classes":
            print("Klassen:", ", ".join(CLASSES))
            continue

        if l.startswith("learn:"):
            try:
                payload = user.split("learn:", 1)[1].strip()
                q, lab = [p.strip() for p in payload.split("=>", 1)]
                fox.learn_pair(q, lab)
                msg = f"Fox: Gelernt → '{q}' => {lab} (Samples: {len(fox.train_texts)})"
                print(msg); speech.say(msg)
            except Exception as e:
                msg = f"Fox: Nutzung: learn: <frage> => <label>. Fehler: {e}"
                print(msg); speech.say(msg)
            continue

        if l.startswith("fact:"):
            try:
                payload = user.split("fact:", 1)[1]
                key, val = [p.strip() for p in payload.split("=", 1)]
                facts = load_json(FACTS_PATH, {})
                facts[key] = val; save_json(FACTS_PATH, facts)
                msg = f"Fox: Gemerkt – {key} = {val}. ({len(facts)} Einträge)"
                print(msg); speech.say(msg)
            except Exception:
                msg = "Fox: Nutzung: fact: <schlüssel> = <wert>"
                print(msg); speech.say(msg)
            continue

        if l.startswith("termin:"):
            payload = user.split("termin:", 1)[1].strip()
            reply = fox.termin(payload, ctx={})
            print("Fox:", reply); speech.say(reply)
            continue

        # === Normaler Dialog ===
        reply = fox.handle(user)
        print("Fox:", reply)
        speech.say(reply)

if __name__ == "__main__":
    main()