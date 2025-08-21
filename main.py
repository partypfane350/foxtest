from __future__ import annotations
import re, time, json, os
from pathlib import Path
from collections import deque

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

from datetime import datetime
try:
    from zoneinfo import ZoneInfo  
except ImportError:
    ZoneInfo = None  


TIMEZONE = os.getenv("FOX_TZ", "Europe/Zurich")

# === Skills ===      
from fox.weather import get_weather    
from fox.mathe import try_auto_calc    

# ========= Pfade =========
MODEL_PATH    = Path("fox_intent.pkl")
TRAIN_PATH    = "train_data.json"
FACTS_PATH    = "facts.json"
CALENDAR_PATH = "calendar.json"

# ========= Labels (nur was geroutet wird) =========
CLASSES = [
    "smalltalk",
    "geo",        
    "mathe",     
    "wetter",     
    "wissen",
    "zeitfrage",
    "termin",
]

# Legacy-Mapping (alte Trainingslabels → neue Taxonomie)
def normalize_label(lbl: str) -> str:
    mapping = {
        
        "rechner": "mathe",
        
        "mathfrage": "mathe",
        
        "stadtfrage": "geo",
        
        "kontinentfrage": "geo",
        
        "termine": "termin",
        
        "zeitfrage": "zeitfrage",
        
        "wetter": "wetter",

    }
    return mapping.get(lbl, lbl)

# ========= JSON-Utils =========
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ========= Start-Trainingsdaten (kurz, alte Labels bleiben – werden normalisiert) =========
train_texts = [
    "Wie geht es dir?","Erzähl mir einen Witz","Hallo Fox","Was kannst du alles?",
    "Was ist 2 + 2?","Was ist 3 * 5?","Was ist 10 - 4?","Was ist 8 / 2?",
    "Welche Städte gibt es in Deutschland?","Liste alle Städte in Japan",
    "Welche Kontinente gibt es?","Nenne mir alle Kontinente",
    "Wie spät ist es?","Sag mir die Uhrzeit",
    "Wie ist das Wetter heute?","Wie wird das Wetter morgen?",
    "Wer hat die Relativitätstheorie entwickelt?","Was ist die größte Stadt der Welt?",
    "Wann ist Weihnachten?","Wann ist dein Geburtstag?"
]
train_labels = [
    "smalltalk","smalltalk","smalltalk","smalltalk",
    "mathfrage","mathfrage","mathfrage","mathfrage",
    "stadtfrage","stadtfrage",
    "kontinentfrage","kontinentfrage",
    "zeitfrage","zeitfrage",
    "wetter","wetter",
    "wissen","wissen",
    "termine","termine"
]
persisted = load_json(TRAIN_PATH, {"texts": [], "labels": []})
if persisted.get("texts"):  train_texts += persisted["texts"]
if persisted.get("labels"): train_labels += persisted["labels"]

# ========= Intent-Model =========
vectorizer: TfidfVectorizer | None = None
clf: SGDClassifier | None = None

def fit_fresh():
    global vectorizer, clf
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(train_texts)
    clf = SGDClassifier(loss="log_loss", max_iter=1000, tol=1e-3, random_state=42)
    clf.fit(X, train_labels)
    joblib.dump((clf, vectorizer, {"n_samples": len(train_texts)}), MODEL_PATH)

def build_or_load():
    global vectorizer, clf
    if MODEL_PATH.exists():
        data = joblib.load(MODEL_PATH)
        if isinstance(data, tuple) and len(data) == 3:
            clf, vectorizer, _ = data
        else:
            clf, vectorizer = data
    else:
        fit_fresh()

# ========= Slots (nur Datum/Uhrzeit – Ort wird NICHT vorgelöst) =========
WEEKDAYS = ["montag","dienstag","mittwoch","donnerstag","freitag","samstag","sonntag"]
def extract_datetime(text: str):
    t = (text or "").lower()
    when = "heute" if "heute" in t else ("morgen" if "morgen" in t else None)
    if not when:
        for wd in WEEKDAYS:
            if wd in t: when = wd; break
    m = re.search(r"(\d{1,2})[:.](\d{2})", t)
    clock = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}" if m else None
    return {"when": when, "time": clock}

# ========= Skills =========
def smalltalk_skill(text, ctx):
    if "witz" in (text or "").lower():
        return "Treffen sich zwei Bytes. Sagt das eine: 'WLAN hier?' — 'Nee, nur LAN.'"
    return "Alles gut! Was brauchst du?"

def time_skill(text, ctx):
    tz = ZoneInfo(TIMEZONE) if ZoneInfo else None
    now = datetime.now(tz) if tz else datetime.now()
    t = text.lower() if text else ""
    if "datum" in t or "tag" in t:
        return f"Heute ist {now:%A, %d.%m.%Y} – es ist {now:%H:%M}"
    return f"Es ist gerade {now:%H:%M}"

def mathe_skill(text, ctx):
    res = try_auto_calc(text)
    return f"Ergebnis: {res}" if res is not None else "Sag mir einen Ausdruck, z. B. 12*7."

def geo_info_skill(text, ctx):
    from fox.geo import geo_skill
    return geo_skill(text, ctx)

def weather_skill(text, ctx):
    m = re.search(r"\bin\s+(.+)$", text or "", flags=re.IGNORECASE)
    q = (m.group(1) if m else text or "").strip()
    if not q:
        return "Sag mir eine Stadt für Wetter (z. B. 'Wetter in Bern')."
    return get_weather(q)

def wiki_skill(text, ctx):
    return "(Demo) Wissensfrage – später Wikipedia/DB anbinden."

def calendar_skill(text, ctx):
    dt = extract_datetime(text)
    if not dt["when"] and not dt["time"]:
        return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."
    evts = load_json(CALENDAR_PATH, [])
    evts.append({"text": text, "when": dt["when"], "time": dt["time"]})
    save_json(CALENDAR_PATH, evts)
    return f"Okay, Termin gespeichert: {(dt['when'] or '')} {(dt['time'] or '')}".strip()

def fallback_skill(text, ctx):
    return "Das weiß ich noch nicht. Erklär mir kurz, was du brauchst – dann lerne ich es."

# ========= Routing =========
def route(label, text, ctx):
    label = normalize_label(label)

    if label == "smalltalk":  return smalltalk_skill(text, ctx)
    if label == "zeitfrage":  return time_skill(text, ctx)

    if label == "geo":        return geo_info_skill(text, ctx)   # nur Infos aus DB
    if label == "wissen":     return wiki_skill(text, ctx)

    if label == "wetter":     return weather_skill(text, ctx)    # NUR wenn explizit gefragt
    if label == "mathe":      return mathe_skill(text, ctx)

    if label == "termin":     return calendar_skill(text, ctx)

    return fallback_skill(text, ctx)

# ========= Orchestrator =========
memory = deque(maxlen=200)

def handle(user: str) -> str:
    # Schnelles Mathe-Autodetect – unabhängig von Intent
    auto = try_auto_calc(user)
    if auto is not None:
        reply = f"Das Ergebnis ist {round(auto, 6)}."
        memory.append({"user": user, "fox": reply, "via": "auto-mathe"})
        return reply

    X = vectorizer.transform([user])
    proba = clf.predict_proba(X)[0]
    idx = int(proba.argmax())
    label = normalize_label(clf.classes_[idx])
    conf = float(proba[idx])

    slots = extract_datetime(user)

    # Keine automatische Geo-Ortserkennung hier – Geo & Wetter bleiben getrennt

    if label == "termin" and not (slots["when"] or slots["time"]):
        return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."

    if conf < 0.6:
        reply = fallback_skill(user, {"slots": slots, "memory": list(memory), "conf": conf})
        memory.append({"user": user, "fox": reply, "label": label, "conf": conf})
        return reply

    reply = route(label, user, {"slots": slots, "memory": list(memory), "conf": conf})
    memory.append({"user": user, "fox": reply, "label": label, "conf": conf})
    return reply

# ========= CLI =========
def main():
    print("🦊 Fox Assistant (clean) – Befehle:")
    print("  learn: <frage> => <label>")
    print("  fact: <key> = <val>")
    print("  termin: <beschreibung>")
    print("  save | reload | showmem | showtrain | quit\n")

    build_or_load()

    while True:
        try: user = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCiao!"); break
        if not user: continue
        l = user.lower()

        if l in ("quit","exit"): print("Bis bald!"); break
        if l == "save":
            joblib.dump((clf, vectorizer, {"n_samples": len(train_texts)}), MODEL_PATH)
            print(f"Fox: Modell gespeichert → {MODEL_PATH}")
            save_json(TRAIN_PATH, {"texts": train_texts, "labels": train_labels})
            print("Fox: Trainingsdaten gespeichert ✅")
            continue
        if l == "reload": build_or_load(); print("Fox: Modell neu geladen."); continue
        if l == "showmem": print(json.dumps(list(memory), ensure_ascii=False, indent=2)); continue
        if l == "showtrain": print(json.dumps({"texts": train_texts, "labels": train_labels}, ensure_ascii=False, indent=2)); continue

        if l.startswith("learn:"):
            try:
                payload = user.split("learn:", 1)[1].strip()
                q, lab = [p.strip() for p in payload.split("=>", 1)]
                train_texts.append(q); train_labels.append(lab)
                fit_fresh()
                print(f"Fox: Gelernt → '{q}' => {lab} (Samples: {len(train_texts)})")
            except Exception:
                print("Fox: Nutzung: learn: <frage> => <label>")
            continue

        if l.startswith("fact:"):
            try:
                payload = user.split("fact:", 1)[1]
                key, val = [p.strip() for p in payload.split("=", 1)]
                facts = load_json(FACTS_PATH, {})
                facts[key] = val; save_json(FACTS_PATH, facts)
                print(f"Fox: Gemerkt – {key} = {val}. ({len(facts)} Einträge)")
            except Exception:
                print("Fox: Nutzung: fact: <schlüssel> = <wert>")
            continue

        if l.startswith("termin:"):
            payload = user.split("termin:", 1)[1].strip()
            dt = extract_datetime(payload)
            cal = load_json(CALENDAR_PATH, [])
            cal.append({"text": payload, "when": dt["when"], "time": dt["time"]})
            save_json(CALENDAR_PATH, cal)
            print(f"Fox: Termin gespeichert → {dt.get('when') or ''} {dt.get('time') or ''} – {payload}".strip())
            continue

        reply = handle(user)
        print("Fox:", reply)

if __name__ == "__main__":
    main()
