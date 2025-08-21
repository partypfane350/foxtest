from __future__ import annotations
import re, time, json, os
from pathlib import Path
from collections import deque

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

# === Skills ===
from fox.weather import get_weather
from fox.geo import geo_skill
from fox.calc import try_auto_calc


# ========= Pfade =========
MODEL_PATH      = Path("fox_intent.pkl")
FACTS_PATH      = "facts.json"
TRAIN_PATH      = "train_data.json"
CALENDAR_PATH   = "calendar.json"

# Alle möglichen Intents (Labels)
CLASSES = [
    # ---- Gespräche ---- 
    "smalltalk",         
    
    # ---- Wissen ----
        # School      
        "geo",
        "rechner"
    ,
        # Allgemein
        "wetter"
        "wissen",
        "zeitfrage",
        
    # ---- Bank ----

    # ---- Machen ----
    "termin"        
]

# ========= JSON-Utils =========
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ========= Start-Trainingsdaten =========
train_texts = [
    
    # Smalltalk
    "Wie geht es dir?", "Erzähl mir einen Witz", "Hallo Fox", "Was kannst du alles?",

    # Mathefragen
    "Was ist 2 + 2?", "Was ist 3 * 5?", "Was ist 10 - 4?", "Was ist 8 / 2?",

    # Stadtfragen
    "Welche Städte gibt es in Deutschland?", "Welche Städte hat Deutschland?",
    "Liste alle Städte in Japan", "Welche Städte gibt es in Italien?",

    # Kontinente
    "Welche Kontinente gibt es?", "Nenne mir alle Kontinente",
    "Was sind die Kontinente der Erde?", "Welche Kontinente kennst du?",

    # Zeitfragen    
    "Wie spät ist es?", "Wie viel Uhr haben wir?", "Sag mir die Uhrzeit", "Was ist die aktuelle Uhrzeit?",

    # Wetterfragen
    "Wie ist das Wetter heute?", "Wie wird das Wetter morgen?",
    "Wird es heute regnen?", "Wie ist die Wettervorhersage für diese Woche?",

    # Wissen
    "wer ist der erste Mensch auf dem Mond?", "Wer hat die Relativitätstheorie entwickelt?",
    "Was ist die größte Stadt der Welt?", "Was ist die kleinste Stadt der Welt?",

    # Termine
    "Wann ist Weihnachten?", "Wann ist Silvester?", "Wann ist der nächste Feiertag?", "Wann ist dein Geburtstag?"
]

train_labels = [
    "smalltalk","smalltalk","smalltalk","smalltalk",
    "mathfrage","mathfrage","mathfrage","mathfrage",
    "stadtfrage","stadtfrage","stadtfrage","stadtfrage",
    "kontinentfrage","kontinentfrage","kontinentfrage","kontinentfrage",
    "zeitfrage","zeitfrage","zeitfrage","zeitfrage",
    "wetter","wetter","wetter","wetter",
    "wissen","wissen","wissen","wissen",
    "termine","termine","termine","termine"
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
    hist = {"n_samples": len(train_texts)}
    joblib.dump((clf, vectorizer, hist), MODEL_PATH)
    return hist

def build_or_load():
    global vectorizer, clf
    if MODEL_PATH.exists():
        data = joblib.load(MODEL_PATH)
        if isinstance(data, tuple) and len(data) == 3:
            clf_loaded, vec_loaded, hist = data
        else:
            clf_loaded, vec_loaded = data
            hist = {"n_samples": "?"}
        clf, vectorizer = clf_loaded, vec_loaded
        return hist
    return fit_fresh()

def refit_after_learn():
    hist = fit_fresh()
    return hist

# ========= Slots =========
WEEKDAYS = ["montag","dienstag","mittwoch","donnerstag","freitag","samstag","sonntag"]
def extract_datetime(text: str):
    t = text.lower()
    when = None
    if "heute" in t: when = "heute"
    elif "morgen" in t: when = "morgen"
    else:
        for wd in WEEKDAYS:
            if wd in t: when = wd; break

    m = re.search(r"(\d{1,2})[:.](\d{2})", t)
    clock = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}" if m else None
    return {"when": when, "time": clock}

# ========= Speicher-Funktionen =========
def add_fact(key: str, value: str):
    facts = load_json(FACTS_PATH, {})
    facts[key] = value
    save_json(FACTS_PATH, facts)
    return facts

def add_training(text: str, label: str):
    data = load_json(TRAIN_PATH, {"texts": [], "labels": []})
    data["texts"].append(text); data["labels"].append(label)
    save_json(TRAIN_PATH, data)

def add_event_free(text: str):
    evts = load_json(CALENDAR_PATH, [])
    dt = extract_datetime(text)
    evts.append({"text": text, "when": dt["when"], "time": dt["time"]})
    save_json(CALENDAR_PATH, evts)
    return evts[-1]

# ========= Skills =========
def smalltalk_skill(text, ctx):
    if "witz" in text.lower():
        return "Treffen sich zwei Bytes. Sagt das eine: 'WLAN hier?' — 'Nee, nur LAN.'"
    return "Alles gut! Was brauchst du?"

def time_skill(text, ctx):
    return "Es ist gerade " + time.strftime("%H:%M")

def calc_skill(text, ctx):
    res = try_auto_calc(text)
    return f"Ergebnis: {res}" if res is not None else "Sag mir einen Ausdruck, z. B. 12*7."

def weather_skill(text, ctx):
    loc = geo_skill(text, ctx)
    if not loc: 
        return "Sag mir einen Ort für Wetter (z. B. in Bern)."
    return get_weather(loc)

def geo_skill_main(text, ctx):
    return geo_skill(text, ctx)

def wiki_skill(text, ctx):
    return "(Demo) Wissensfrage – später Wikipedia/DB anbinden."

def calendar_skill(text, ctx):
    dt = extract_datetime(text)
    if not dt["when"] and not dt["time"]:
        return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."
    ev = add_event_free(text)
    return f"Okay, Termin gespeichert: {ev.get('when') or ''} {ev.get('time') or ''}".strip()

def fallback_skill(text, ctx):
    return "Das weiß ich noch nicht. Erklär mir kurz, was du brauchst – dann lerne ich es."

# ========= Routing =========
def route(label, text, ctx):
    
    # ---- Gespräch ----
    if label == "smalltalk":
        return smalltalk_skill(text, ctx)
  

    # ---- Wissen ----
        
        # School
    if label == "geo":
        return geo_skill_main(text, ctx)
   
    if label == "rechner":
        return calc_skill(text, ctx)

        # Allgemein 
    if label == "wetter":
        return weather_skill(text, ctx)
   
    if label == "wissen":
        return wiki_skill(text, ctx)
    
    if label == "zeitfrage":
        return time_skill(text, ctx)


    # ---- Bank ----


    # ---- Machen ----
    if label == "termin":
        return calendar_skill(text, ctx)


    # ---- Fallback ----
    return fallback_skill(text, ctx)


# ========= Orchestrator =========
memory = deque(maxlen=200)

def handle(user: str) -> str:
    auto = try_auto_calc(user)
    if auto is not None:
        reply = f"Das Ergebnis ist {round(auto, 6)}."
        memory.append({"user": user, "fox": reply, "via": "auto-calc"})
        return reply

    X = vectorizer.transform([user])
    proba = clf.predict_proba(X)[0]
    idx = int(proba.argmax())
    label = clf.classes_[idx]
    conf = float(proba[idx])

    slots = extract_datetime(user)
    slots["where"] = geo_skill(user, {"slots": slots, "memory": list(memory)})

    if label == "wetter" and not slots["where"]:
        return "Für Wetter brauche ich noch einen Ort (z. B. 'in Bern')."
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
    print("🦊 Fox Assistant – mit Speicher")
    print("Befehle:")
    print("  learn: <frage> => <label>")
    print("  fact: <key> = <val>")
    print("  termin: <beschreibung>")
    print("  save | reload | showmem | showfacts | showtrain | showcal | quit\n")

    hist = build_or_load()
    print(f"[i] Modell geladen – Beispiele: {hist['n_samples']}")

    while True:
        try: user = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCiao!"); break
        if not user: continue
        l = user.lower()

        if l in ("quit","exit"): 
            print("Bis bald!"); 
            break
        
        if l == "save":
            joblib.dump((clf, vectorizer, {"n_samples": len(train_texts)}), MODEL_PATH)
            print(f"Fox: Modell gespeichert → {MODEL_PATH}")
            print("Fox: Trainingsdaten sind bereits fix in train_data.json gespeichert ✅")
            continue
        
        if l == "reload": 
            build_or_load(); 
            print("Fox: Modell neu geladen."); 
            continue
        
        if l == "showmem": 
            print(json.dumps(list(memory), ensure_ascii=False, indent=2)); 
            continue
        
        if l == "showfacts": 
            print(json.dumps(load_json(FACTS_PATH, {}), ensure_ascii=False, indent=2)); 
            continue
        
        if l == "showtrain": 
            print(json.dumps(load_json(TRAIN_PATH, {"texts": [], "labels": []}), ensure_ascii=False, indent=2)); 
            continue
        
        if l == "showcal": 
            print(json.dumps(load_json(CALENDAR_PATH, []), ensure_ascii=False, indent=2)); 
            continue

        if l.startswith("learn:"):
            try:
                payload = user.split("learn:", 1)[1].strip()
                q, lab = [p.strip() for p in payload.split("=>", 1)]
                if lab not in CLASSES:
                    print("Fox: Unbekanntes Label. Erlaubt:", ", ".join(CLASSES)); continue
                add_training(q, lab)
                train_texts.append(q); train_labels.append(lab)
                hist = refit_after_learn()
                print(f"Fox: Gelernt → '{q}' => {lab} (Samples: {hist['n_samples']})")
            except Exception:
                print("Fox: Nutzung: learn: <frage> => <label>")
            continue

        if l.startswith("fact:"):
            try:
                payload = user.split("fact:", 1)[1]
                key, val = [p.strip() for p in payload.split("=", 1)]
                facts = add_fact(key, val)
                print(f"Fox: Gemerkt – {key} = {val}. ({len(facts)} Einträge)")
            except Exception:
                print("Fox: Nutzung: fact: <schlüssel> = <wert>")
            continue

        if l.startswith("termin:"):
            payload = user.split("termin:", 1)[1].strip()
            ev = add_event_free(payload)
            print(f"Fox: Termin gespeichert → {ev.get('when') or ''} {ev.get('time') or ''} – {payload}".strip())
            continue

        reply = handle(user)
        print("Fox:", reply)

if __name__ == "__main__":
    main()
