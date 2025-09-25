from __future__ import annotations

import os
import re
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from collections import deque
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier

# ===== Skills zentral laden =====
from fox.skills import (
    geo_skill,
    get_weather,
    mathe_skill,
    try_auto_calc,
    time_skill,
    gespraech_skill,
    termin_skill,
    init_knowledge_db,
    set_fact,
    get_fact,
    search_facts,
)

# ===== Sprach Ein-/Ausgabe =====
from fox.speech import SpeechIn, Speech
import sounddevice as sd

# ===== Labels =====
import fox.labels as labels
from fox.labels import CLASSES, LEGACY_MAP, WEEKDAYS, BASE_TRAIN

# ===== Snapshots =====
from backup import make_snapshot

from dotenv import load_dotenv
load_dotenv()

# =========================
# Konfiguration & Konstanten
# =========================
MODEL_PATH       = Path("fox_intent.pkl")
CALENDAR_PATH    = Path("calendar.json")

CONF_THRESHOLD   = 0.60
SIM_THRESHOLD    = 0.72
MEMORY_SIZE      = 200
RANDOM_STATE     = 42
MLP_MAX_ITER     = 400

AUTO_LEARN            = True
AUTO_LEARN_MIN_CONF   = 0.15
AUTO_LEARN_MAX_LEN    = 120
AUTO_LEARN_BLACKLIST  = {}

LOG_LEVEL = os.getenv("FOX_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fox")
for name in ("comtypes", "comtypes.client", "comtypes.gen", "pyttsx3"):
    lg = logging.getLogger(name)
    lg.setLevel(logging.WARNING)
    lg.propagate = False

# ======================
# Knowledge-DB (Training)
# ======================
def _knowledge_db_path() -> Path:
    root = Path("knowledge.db")
    if root.exists():
        return root
    fox_db = Path(__file__).resolve().parent / "fox" / "knowledge.db"
    if fox_db.exists():
        return fox_db
    return root

def _open_knowledge():
    p = _knowledge_db_path()
    con = sqlite3.connect(p)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    return con

def _ensure_training_table():
    try:
        with _open_knowledge() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS training(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text  TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at REAL
                )
            """)
            con.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_training_unique
                ON training(text, label)
            """)
            con.commit()
    except Exception as e:
        log.warning("Konnte training-Tabelle nicht anlegen: %s", e)

def db_add_training_pair(text: str, label: str) -> None:
    text = (text or "").strip()
    label = (label or "").strip()
    if not text or not label:
        return
    _ensure_training_table()
    with _open_knowledge() as con:
        con.execute(
            "INSERT OR IGNORE INTO training(text,label,created_at) VALUES(?,?,?)",
            (text, label, datetime.now().timestamp())
        )
        con.commit()

def db_list_training() -> list[tuple[str, str]]:
    _ensure_training_table()
    with _open_knowledge() as con:
        cur = con.execute("SELECT text, label FROM training ORDER BY id ASC")
        return [(t, l) for (t, l) in cur.fetchall()]

# ======================
# Utils / Helfer
# ======================
def normalize_label(lbl: str) -> str:
    return LEGACY_MAP.get(lbl, lbl)

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

TIME_TRIGGERS    = ("uhr", "zeit", "datum", "tag", "heute", "morgen")
WEATHER_TRIGGERS = ("wetter", "temperatur", "grad", "kalt", "heiss", "heiß", "regen", "sonnig", "sturm", "schnee")

def has_time_trigger(s: str) -> bool:
    s = (s or "").lower()
    return any(k in s for k in TIME_TRIGGERS)

def has_weather_trigger(s: str) -> bool:
    s = (s or "").lower()
    return any(k in s for k in WEATHER_TRIGGERS)

def extract_weather_query(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    m = re.search(r"\b(?:in|von|für|bei)\s+([A-Za-zÄÖÜäöüß\-’' ]{2,})$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t

def format_topk(pairs: list[tuple[str, float]]) -> str:
    return "   ".join(f"{i}) {lab} {round(p*100):d}%" for i, (lab, p) in enumerate(pairs, 1))

def process_input(fox, speech: Speech, user_text: str) -> None:
    user_text = (user_text or "").strip()
    if not user_text:
        return
    reply = fox.handle(user_text)
    print("Fox:", reply)
    speech.say(reply)

# ===========================
# ML: Vektorisierer & Klassif.
# ===========================
@dataclass
class IntentModel:
    clf: MLPClassifier
    vectorizer: TfidfVectorizer
    meta: Dict[str, Any]

    @staticmethod
    def fit_from_texts(texts: List[str], labels_: List[str]) -> "IntentModel":
        vec = TfidfVectorizer(ngram_range=(1, 2), lowercase=True, strip_accents=None, min_df=1)
        X = vec.fit_transform(texts)
        clf = MLPClassifier(
            hidden_layer_sizes=(512, 256),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            max_iter=MLP_MAX_ITER,
            early_stopping=True,
            random_state=RANDOM_STATE,
            verbose=False
        )
        clf.fit(X, labels_)
        meta = {"n_samples": len(texts), "trained_at": datetime.now().isoformat(timespec="seconds")}
        return IntentModel(clf=clf, vectorizer=vec, meta=meta)

    def save(self, path: Path) -> None:
        joblib.dump((self.clf, self.vectorizer, self.meta), path)

    @staticmethod
    def load(path: Path) -> "IntentModel":
        data = joblib.load(path)
        if isinstance(data, tuple) and len(data) == 3:
            clf, vec, meta = data
        else:
            clf, vec = data
            meta = {}
        return IntentModel(clf=clf, vectorizer=vec, meta=meta)

# ==========================
# Fox Assistant Core
# ==========================
class FoxAssistant:
    def __init__(self):
        self.memory = deque(maxlen=MEMORY_SIZE)
        self._load_training_from_db()

        # Modell laden oder trainieren
        if MODEL_PATH.exists():
            self.model = IntentModel.load(MODEL_PATH)
            log.info("Modell geladen (%s).", MODEL_PATH)
        else:
            self.model = IntentModel.fit_from_texts(self.train_texts, self.train_labels)
            self.model.save(MODEL_PATH)
            log.info("Modell neu trainiert (%d Samples).", len(self.train_texts))

        self.last_input: Optional[str] = None
        self.last_topk: List[tuple[str, float]] = []
        self._rebuild_train_matrix()

    def _load_training_from_db(self) -> None:
        persisted = db_list_training() or []
        base_texts = list(BASE_TRAIN["texts"])
        base_labels = list(BASE_TRAIN["labels"])
        add_texts  = [t for (t, _) in persisted]
        add_labels = [l for (_, l) in persisted]
        pairs = list(dict.fromkeys(zip(base_texts + add_texts, base_labels + add_labels)))
        if pairs:
            self.train_texts, self.train_labels = map(list, zip(*pairs))
        else:
            self.train_texts, self.train_labels = [], []

    def _rebuild_train_matrix(self) -> None:
        try:
            self.train_X = self.model.vectorizer.transform(self.train_texts)
        except Exception:
            from scipy.sparse import csr_matrix
            self.train_X = csr_matrix((0, 0))
        self._train_texts_lc = set((t or "").strip().lower() for t in self.train_texts)

    def label_for_exact_text(self, text: str) -> Optional[str]:
        t = (text or "").strip().lower()
        for tt, ll in zip(self.train_texts, self.train_labels):
            if (tt or "").strip().lower() == t:
                return ll
        return None

    def is_known_text(self, text: str) -> tuple[bool, float]:
        t = (text or "").strip()
        if not t: return (False, 0.0)
        if t.lower() in self._train_texts_lc: return (True, 1.0)
        try:
            x = self.model.vectorizer.transform([t])
            if getattr(self, "train_X", None) is None or self.train_X.shape[0] == 0:
                return (False, 0.0)
            sims = (self.train_X @ x.T).toarray().ravel()
            max_sim = float(sims.max()) if sims.size else 0.0
            return (max_sim >= SIM_THRESHOLD, max_sim)
        except Exception:
            return (False, 0.0)

    # ===== Routing =====
    def route(self, label: str, text: str, ctx: Dict[str, Any]) -> str:
        label = normalize_label(label)
        slots = ctx.get("slots", {})
        if label == "gespräch":  return gespraech_skill(text, ctx)
        if label == "time":      return time_skill(text, ctx)
        if label == "geo":       return geo_skill(text, ctx)
        if label == "wissen":    return self.do_wissen(text)
        if label == "wetter":    return self.do_wetter(text)
        if label == "mathe":     return self.do_mathe(text)
        if label == "termin":    return self.do_termin(text)
        return self.fallback(text, ctx)

    def do_wissen(self, text: str) -> str:
        val = get_fact(text) or get_fact(text.lower())
        if val: return str(val)
        return "Ich kenne dazu noch keine Antwort."

    def do_wetter(self, text: str) -> str:
        q = extract_weather_query(text)
        if not q: return "Sag mir eine Stadt für Wetter (z. B. 'Wetter in Bern')."
        return get_weather(q)

    def do_mathe(self, text: str) -> str:
        res = try_auto_calc(text)
        if res is not None:
            return f"Ergebnis: {res}"
        return mathe_skill(text, {})

    def do_termin(self, text: str, ctx: Dict[str, Any] = {}) -> str:
        slots = extract_datetime(text)
        if not (slots["when"] or slots["time"]):
            return "Für den Termin brauche ich Datum/Zeit."
        return termin_skill(text, ctx)

    def fallback(self, text: str, ctx: Dict[str, Any] = {}) -> str:
        return "Das weiß ich (noch) nicht."

    # ===== Prediction =====
    def topk_predict(self, text: str, k: int = 3) -> List[tuple[str, float]]:
        X = self.model.vectorizer.transform([text])
        proba = self.model.clf.predict_proba(X)[0]
        classes = [normalize_label(c) for c in self.model.clf.classes_]
        pairs = list(zip(classes, proba))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:k]

    # ===== Handle =====
    def handle(self, user: str) -> str:
        t = (user or "").strip()
        if not t: return ""

        auto = try_auto_calc(t)
        if auto is not None:
            reply = f"Das Ergebnis ist {round(auto, 6)}."
            self.memory.append({"user": t, "fox": reply, "via": "auto-mathe"})
            return reply

        X = self.model.vectorizer.transform([t])
        proba = self.model.clf.predict_proba(X)[0]
        idx = int(proba.argmax())
        label = normalize_label(self.model.clf.classes_[idx])
        conf = float(proba[idx])

        self.last_input = t
        try: self.last_topk = self.topk_predict(t, k=3)
        except Exception: self.last_topk = []

        known, _ = self.is_known_text(t)
        exact_lbl = self.label_for_exact_text(t)
        if exact_lbl:
            label = normalize_label(exact_lbl)
            conf = max(conf, 0.999)
        if has_weather_trigger(t):
            label = "wetter"; conf = max(conf, 0.66)
        elif has_time_trigger(t):
            label = "time"; conf = max(conf, 0.66)

        if known or conf >= CONF_THRESHOLD:
            reply = self.route(label, t, {"conf": conf})
            self.memory.append({"user": t, "fox": reply, "label": label, "conf": conf, "via": "direct"})
            return reply

        reply = self.fallback(t, {"conf": conf})
        self.memory.append({"user": t, "fox": reply, "label": label, "conf": conf, "via": "fallback"})
        return reply

    # ===== Persistenz / Lernen =====
    def fit_fresh(self) -> None:
        self.model = IntentModel.fit_from_texts(self.train_texts, self.train_labels)
        self.model.save(MODEL_PATH)
        self._rebuild_train_matrix()
        log.info("Neu trainiert (%d Samples).", len(self.train_texts))

    def learn_pair(self, question: str, label: str) -> None:
        label = normalize_label(label)
        if label not in CLASSES:
            raise ValueError(f"Unbekanntes Label '{label}'.")
        q = (question or "").strip()
        if not q: raise ValueError("Leere Eingabe kann nicht gelernt werden.")
        db_add_training_pair(q, label)
        self._load_training_from_db()
        self.fit_fresh()
        self.save_all()
        make_snapshot([MODEL_PATH, _knowledge_db_path()], tag="learn")

    def save_all(self) -> None:
        self.model.save(MODEL_PATH)
        self._rebuild_train_matrix()
        log.info("Modell gespeichert & Index aktualisiert.")

# ========= CLI-Loop =========
def main():
    print("🦊 Fox Assistant — Befehle:")
    print(labels.LABEL_TEXTS["cli"]["help"].rstrip())
    fox = FoxAssistant()
    speech = Speech(enabled=True)
    mic = SpeechIn(model_name="small", lang="de")

    _ensure_training_table()
    init_knowledge_db()

    while True:
        try: user = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCiao!"); break
        if not user: continue
        l = user.lower()

        if l in ("quit", "exit"):
            print("Bis bald!"); break
        if l == "save": fox.save_all(); print("Fox: Modell gespeichert."); continue
        if l.startswith("merke:"):
            try:
                key, val = [p.strip() for p in user.split("merke:",1)[1].split("=",1)]
                set_fact(key.lower(), val); print(f"Gemerkt: {key} = {val}"); continue
            except Exception: print("Fehler bei 'merke'"); continue
        process_input(fox, speech, user)

if __name__ == "__main__":
    main()
