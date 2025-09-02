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
from sklearn.linear_model import SGDClassifier

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
    # add_training_pair, list_training   # (optional – falls dein skills/__init__.py das schon exportiert)
)

# ===== Sprach Ein-/Ausgabe =====
from fox.speech import SpeechIn, Speech
import sounddevice as sd

# ===== Labels (Aggregat) =====
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
SGD_MAX_ITER     = 1000
SGD_TOL          = 1e-3

AUTO_LEARN            = True
AUTO_LEARN_MIN_CONF   = 0.15
AUTO_LEARN_MAX_LEN    = 120
AUTO_LEARN_BLACKLIST  = {}

SHOW_TIPS       = False
WIKI_TIMEOUT    = 5

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
    """
    Bevorzugt knowledge.db im Projekt-Root.
    Falls nicht vorhanden: fox/knowledge.db (ältere Struktur).
    """
    root = Path("knowledge.db")
    if root.exists():
        return root
    fox_db = Path(__file__).resolve().parent / "fox" / "knowledge.db"
    if fox_db.exists():
        return fox_db
    return root  # neu im Root anlegen

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
    TRIG = r"(?:wetter|temperatur|grad|kalt|heiß|heiss|regen|sonnig|sturm|schnee)"
    m2 = re.search(rf"\b{TRIG}\b\s+([A-Za-zÄÖÜäöüß\-’' ]{{2,}})$", t, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    if re.search(rf"\b{TRIG}\b", t, re.IGNORECASE):
        tokens = re.findall(r"[A-Za-zÄÖÜäöüß\-’']+", t)
        if tokens:
            return " ".join(tokens[-3:]).strip()
    return t

def format_topk(pairs: list[tuple[str, float]]) -> str:
    return "   ".join(f"{i}) {lab} {round(p*100):d}%"
                      for i, (lab, p) in enumerate(pairs, 1))

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
    clf: SGDClassifier
    vectorizer: TfidfVectorizer
    meta: Dict[str, Any]

    @staticmethod
    def fit_from_texts(texts: List[str], labels_: List[str]) -> "IntentModel":
        vec = TfidfVectorizer(ngram_range=(1, 2), lowercase=True, strip_accents=None, min_df=1)
        X = vec.fit_transform(texts)
        clf = SGDClassifier(
            loss="log_loss",
            max_iter=SGD_MAX_ITER,
            tol=SGD_TOL,
            random_state=RANDOM_STATE,
            alpha=1e-4,
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
# Core Assistant Orchestrator
# ==========================
class FoxAssistant:
    def __init__(self):
        self.memory = deque(maxlen=MEMORY_SIZE)
        self._load_training_from_db()

        # Modell
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

        log.info("Knowledge-DB Pfad (Training): %s", _knowledge_db_path())

    # ===== Training laden =====
    def _load_training_from_db(self) -> None:
        """BASE_TRAIN + persistente Paare aus knowledge.db/training."""
        persisted = db_list_training() or []   # [(text,label), ...]
        base_texts = list(BASE_TRAIN["texts"])
        base_labels = list(BASE_TRAIN["labels"])
        add_texts  = [t for (t, _) in persisted]
        add_labels = [l for (_, l) in persisted]
        texts = base_texts + add_texts
        labels_ = base_labels + add_labels
        # dedupe (text,label)
        pairs = list(dict.fromkeys(zip(texts, labels_)))
        self.train_texts, self.train_labels = map(list, zip(*pairs)) if pairs else ([], [])

    # ===== Index/Ähnlichkeit =====
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
        if not t:
            return (False, 0.0)
        if t.lower() in self._train_texts_lc:
            return (True, 1.0)
        try:
            x = self.model.vectorizer.transform([t])
            if getattr(self, "train_X", None) is None or self.train_X.shape[0] == 0:
                return (False, 0.0)
            sims = (self.train_X @ x.T).toarray().ravel()
            max_sim = float(sims.max()) if sims.size else 0.0
            return (max_sim >= SIM_THRESHOLD, max_sim)
        except Exception:
            return (False, 0.0)

    # ===== Routing (Skills) =====
    def do_gespraech(self, text: str, ctx: Dict[str, Any]) -> str:
        return gespraech_skill(text, ctx)

    def do_mathe(self, text: str, ctx: Dict[str, Any]) -> str:
        res = try_auto_calc(text)
        if res is not None:
            return f"Ergebnis: {res}"
        return mathe_skill(text, ctx)

    def do_geo(self, text: str, ctx: Dict[str, Any]) -> str:
        return geo_skill(text, ctx)

    def do_wetter(self, text: str, ctx: Dict[str, Any]) -> str:
        q = extract_weather_query(text)
        if not q:
            return "Sag mir eine Stadt für Wetter (z. B. 'Wetter in Bern')."
        return get_weather(q)

    def _wiki_summary(self, query: str, lang: str = "de") -> Optional[str]:
        import requests
        try:
            t = (query or "").strip()
            if not t:
                return None
            r1 = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={
                "action": "query", "list": "search", "srsearch": t, "format": "json", "srlimit": 1
            }, timeout=WIKI_TIMEOUT)
            hits = (r1.json().get("query") or {}).get("search") or []
            if not hits:
                return None
            title = hits[0].get("title")
            if not title:
                return None
            r2 = requests.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}", timeout=WIKI_TIMEOUT)
            js = r2.json()
            summ = js.get("extract") or js.get("description")
            if not summ:
                return None
            summ = summ.strip()
            if len(summ) > 480:
                summ = summ[:470].rstrip() + " …"
            return f"{title}: {summ}"
        except Exception:
            return None

    def _search_facts_best(self, q: str) -> Optional[tuple[str, str, float]]:
        try:
            rows = search_facts(q)  # [(key, value), ...]
        except Exception:
            rows = []
        if not rows:
            return None
        import re as _re
        def toks(s: str):
            return set(_re.findall(r"[a-z0-9äöüß]+", (s or "").lower()))
        qset = toks(q)
        scored = []
        for key, val in rows:
            score = 0.0
            score = max(score, len(qset & toks(key)) / (len(qset) or 1))
            score = max(score, len(qset & toks(val)) / (len(qset) or 1))
            scored.append((key, val, score))
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[0] if scored else None

    def do_wissen(self, text: str, ctx: Dict[str, Any]) -> str:
        q = (text or "").strip()
        try:
            val = get_fact(q) or get_fact(q.lower())
        except Exception:
            val = None
        if val:
            return str(val)

        hit = self._search_facts_best(q)
        if hit and hit[2] >= 0.25:
            key, val2, score = hit
            return f"{val2}  (aus Wissen: {key}, match={score:.2f})"

        ans = self._wiki_summary(q, lang="de")
        if ans:
            return ans + "\n\n(Hinweis: Quelle Wikipedia-Kurzfassung)"

        return "Dazu kenne ich noch keine gute Antwort. Sag mir kurz die richtige – ich lerne es."

    def do_termin(self, text: str, ctx: Dict[str, Any]) -> str:
        dt = extract_datetime(text)
        if not (dt["when"] or dt["time"]):
            return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."
        return termin_skill(text, ctx)

    def do_time(self, text: str, ctx: Dict[str, Any]) -> str:
        return time_skill(text, ctx)

    def fallback(self, text: str, ctx: Dict[str, Any]) -> str:
        conf = ctx.get("conf")
        if conf is not None:
            return f"Das weiß ich (noch) nicht (conf={conf:.2f}). Erklär mir kurz, was du brauchst – dann lerne ich es."
        return "Das weiß ich (noch) nicht. Erklär mir kurz, was du brauchst – dann lerne ich es."

    # ===== Routing =====
    def route(self, label: str, text: str, ctx: Dict[str, Any]) -> str:
        label = normalize_label(label)
        if label == "gespräch":  return self.do_gespraech(text, ctx)
        if label == "time":      return self.do_time(text, ctx)
        if label == "geo":       return self.do_geo(text, ctx)
        if label == "wissen":    return self.do_wissen(text, ctx)
        if label == "wetter":    return self.do_wetter(text, ctx)
        if label == "mathe":     return self.do_mathe(text, ctx)
        if label == "termin":    return self.do_termin(text, ctx)
        return self.fallback(text, ctx)

    # ===== Top-K =====
    def topk_predict(self, text: str, k: int = 3) -> List[tuple[str, float]]:
        X = self.model.vectorizer.transform([text])
        proba = self.model.clf.predict_proba(X)[0]
        classes = [normalize_label(c) for c in self.model.clf.classes_]
        pairs = list(zip(classes, proba))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:k]

    # ===== Handle (mit Disambiguation) =====
    def handle(self, user: str) -> str:
        # 1) Sofort-Mathe
        auto = try_auto_calc(user)
        if auto is not None:
            reply = f"Das Ergebnis ist {round(auto, 6)}."
            self._memorize(user, reply, via="auto-mathe")
            return reply

        t = (user or "").strip()

        # 2) Modell
        X = self.model.vectorizer.transform([t])
        proba = self.model.clf.predict_proba(X)[0]
        idx = int(proba.argmax())
        label = normalize_label(self.model.clf.classes_[idx])
        conf = float(proba[idx])

        slots = extract_datetime(t)

        # Merken für "c 1" / "c wetter" / "why"
        self.last_input = t
        try:
            self.last_topk = self.topk_predict(t, k=3)
        except Exception:
            self.last_topk = []

        # Bekannt?
        known, max_sim = self.is_known_text(t)

        # Exakt gelernt?
        exact_lbl = self.label_for_exact_text(t)
        if exact_lbl:
            label = normalize_label(exact_lbl)
            conf = max(conf, 0.999)

        # Trigger-Overrides
        if has_weather_trigger(t):
            label = "wetter"; conf = max(conf, 0.66)
        elif has_time_trigger(t):
            label = "time"; conf = max(conf, 0.66)

        # Termin braucht Slots
        if label == "termin" and not (slots["when"] or slots["time"]):
            return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."

        # Direkt antworten
        if known or conf >= CONF_THRESHOLD:
            reply = self.route(label, t, {"slots": slots, "memory": list(self.memory), "conf": conf})
            self._memorize(user, reply, label=label, conf=conf,
                           via=("direct" if known else "confident"))
            return reply

        # Unsicher -> Best-Effort + Kurz-Hinweis + evtl. Autolernen
        best_reply = None
        try:
            best_reply, guess = self._best_effort(t)
        except Exception:
            guess = label
            best_reply = self.fallback(t, {"conf": conf})

        topk_pairs = self.last_topk or [(guess, conf)]
        top_line = format_topk(topk_pairs)

        # Autolernen (vorsichtig)
        can_autolearn = (
            AUTO_LEARN and len(t) <= AUTO_LEARN_MAX_LEN and conf >= AUTO_LEARN_MIN_CONF
            and guess in CLASSES and guess not in AUTO_LEARN_BLACKLIST
            and not re.search(r"https?://|\bwww\.", t)
        )
        if can_autolearn:
            try:
                self.learn_pair(t, guess)   # persistiert in knowledge.db
                best_reply += f"\n(Gelernt: '{t}' => {guess})"
            except Exception as e:
                best_reply += f"\n(Autolernen fehlgeschlagen: {e})"

        hint = (
            f"\n\nUnsicher. Meintest du: {top_line}\n"
            f"Sag: c 1  |  c 2  |  c 3  oder  c <label>  (z.B. c wetter)"
        )
        self._memorize(user, best_reply, label=guess, conf=conf, via="best-effort")
        return best_reply + hint

    # ===== Best-Effort =====
    def _best_effort(self, text: str) -> tuple[str, str]:
        t = (text or "").lower()

        # Gespräch/Begrüßung
        if any(g in t.split() for g in ("hallo","hi","hey","servus","moin","grüezi")) or t.strip() in ("hallo","hi","hey","servus","moin","grüezi"):
            return (gespraech_skill(text, {}), "gespräch")

        # Mathe
        res = try_auto_calc(text)
        if res is not None:
            return (f"Das Ergebnis ist {round(res, 6)}.", "mathe")

        # Wetter
        if has_weather_trigger(t):
            q = extract_weather_query(text)
            rep = get_weather(q or text)
            return (rep, "wetter")

        # Geo
        rep_geo = geo_skill(text, {})
        if rep_geo and "Sag mir einen Ort" not in rep_geo:
            return (rep_geo, "geo")

        # Zeit/Datum
        if has_time_trigger(t):
            return (time_skill(text, {}), "time")

        # Termin-Indizien
        if any(k in t for k in ("termin", "meeting", "arzt", "kalender")) or re.search(r"\d{1,2}[:.]\d{2}", t):
            return (self.do_termin(text, {}), "termin")

        # Fallback Gespräch
        return (gespraech_skill(text, {}), "gespräch")

    def _memorize(self, user: str, reply: str, **meta) -> None:
        self.memory.append({"user": user, "fox": reply, **meta})

    # ===== Snapshots / Training / Persistenz =====
    def snapshot(self, tag: str = "autosave") -> None:
        targets = [
            Path("fox_intent.pkl"),
            Path("calendar.json"),
            _knowledge_db_path(),
        ]
        make_snapshot(targets, tag=tag)

    def fit_fresh(self) -> None:
        self.model = IntentModel.fit_from_texts(self.train_texts, self.train_labels)
        self.model.save(MODEL_PATH)
        self._rebuild_train_matrix()
        log.info("Neu trainiert (%d Samples).", len(self.train_texts))

    def learn_pair(self, question: str, label: str) -> None:
        label = normalize_label(label)
        if label not in CLASSES:
            raise ValueError(f"Unbekanntes Label '{label}'. Erlaubt: {', '.join(CLASSES)}")

        q = (question or "").strip()
        if not q:
            raise ValueError("Leere Eingabe kann nicht gelernt werden.")

        # In DB persistieren (dedupe via UNIQUE)
        db_add_training_pair(q, label)
        # Trainingsbasis neu aus DB ziehen
        self._load_training_from_db()
        self.fit_fresh()
        self.save_all()
        self.snapshot(tag="learn")

    def save_all(self) -> None:
        self.model.save(MODEL_PATH)
        self._rebuild_train_matrix()
        log.info("Modell gespeichert & Index aktualisiert.")


# ========= CLI-Loop =========
def main():
    print("🦊 Fox Assistant — Befehle:")
    print(labels.LABEL_TEXTS["cli"]["help"].rstrip())
    print(f"Labels geladen aus: {labels.__file__}")

    # Knowledge-DB (facts/notes) initialisieren
    try:
        init_knowledge_db()
    except Exception as e:
        print(f"Warnung: Konnte Knowledge-DB nicht initialisieren: {e}")
    _ensure_training_table()

    fox = FoxAssistant()
    speech = Speech(enabled=True)
    mic = SpeechIn(model_name="small", lang="de")   # Whisper

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

        # === Audio-Steuerung ===
        if l == "audio an":
            speech.set_enabled(True); print("Fox: Audio EIN"); continue
        if l == "audio aus":
            speech.set_enabled(False); print("Fox: Audio AUS"); continue

        # === Mikro-Geräte ===
        if l in ("mikro geraete", "mikro geräte", "mikro devices"):
            SpeechIn.list_input_devices(); continue

        if l == "mikro":
            heard = mic.listen_once(max_seconds=8)
            if heard:
                print(f"Du (Mikro): {heard}")
                process_input(fox, speech, heard)   # EINZIGER WEG
            else:
                msg = "Ich habe nichts verstanden."
                print("Fox:", msg); speech.say(msg)
            continue

        if l.startswith("mikro device "):
            try:
                idx = int(l.split()[-1])
                devs = sd.query_devices()
                if idx < 0 or idx >= len(devs):
                    raise ValueError(f"Index {idx} außerhalb (0..{len(devs)-1})")
                if devs[idx].get("max_input_channels", 0) <= 0:
                    raise ValueError(f"Gerät {idx} hat keine Eingabekanäle")
                sd.default.device = (idx, None)
                print(f"Fox: Mikrofon-Eingabegerät auf Index {idx} gesetzt.")
            except Exception as e:
                print(f"Fox: Konnte Gerät nicht setzen: {e}")
            continue

        # === Utility ===
        if l == "save":
            fox.save_all()
            print(f"Fox: Modell gespeichert → {MODEL_PATH}")
            continue

        if l == "backup":
            fox.snapshot(tag="manual")
            print("Fox: Snapshot erstellt (Ordner ./backups).")
            continue

        if l == "reload":
            fox.model = IntentModel.load(MODEL_PATH); fox._rebuild_train_matrix()
            print("Fox: Modell neu geladen.")
            continue

        if l == "labelspath":
            print(f"Fox: Labels-Pfad → {labels.__file__}")
            continue

        if l == "showmem":
            print(json.dumps(list(fox.memory), ensure_ascii=False, indent=2))
            continue

        if l == "showtrain":
            pairs = db_list_training() or []
            print(json.dumps(
                [{"text": t, "label": lab} for (t, lab) in pairs],
                ensure_ascii=False, indent=2
            ))
            continue

        if l == "classes":
            print("Klassen:", ", ".join(CLASSES)); continue

        # === Analyse: warum? ===
        if l == "why":
            if fox.last_input:
                pairs = fox.last_topk or fox.topk_predict(fox.last_input, 3)
                if not pairs:
                    print("Fox: Keine Vorhersage verfügbar."); continue
                pretty = "\n".join([f"- {lab:<10} {p:.2f}" for lab, p in pairs])
                msg = f"Letzte Eingabe: {fox.last_input}\nTop-Vermutungen:\n{pretty}\n\nKorrigieren: c 1 | c 2 | c 3 | c <label>"
                print("Fox:", msg); speech.say("Okay.")
            else:
                print("Fox: Ich habe noch keine letzte Eingabe gemerkt.")
            continue

        # === Kurzes Korrigieren: "c 1" | "c <label>" ===
        if l.startswith("c "):
            try:
                if not fox.last_input:
                    print("Fox: Keine letzte Eingabe vorhanden."); continue
                arg = l.split("c", 1)[1].strip()
                # Zahl 1..3 -> aus TopK
                if arg.isdigit():
                    i = int(arg)
                    if i < 1 or i > 3 or not fox.last_topk or i > len(fox.last_topk):
                        raise ValueError("Index außerhalb 1..3")
                    chosen_label = fox.last_topk[i-1][0]
                else:
                    chosen_label = arg
                fox.learn_pair(fox.last_input, chosen_label)
                msg = f"Fox: Gespeichert → '{fox.last_input}' => {chosen_label}"
                print(msg); speech.say("Gespeichert.")
            except Exception as e:
                print(f"Fox: Konnte nicht speichern: {e}")
            continue

        # === Langer Korrigieren-Weg bleibt kompatibel ===
        if l.startswith("correct:"):
            try:
                payload = user.split("correct:", 1)[1].strip()
                if "=>" in payload:
                    q, lab = [p.strip() for p in payload.split("=>", 1)]
                else:
                    if not fox.last_input:
                        print("Fox: Keine letzte Eingabe vorhanden. Nutze: correct: <text> => <label>")
                        continue
                    q, lab = fox.last_input, payload
                fox.learn_pair(q, lab)
                msg = f"Fox: Korrektur gelernt → '{q}' => {lab} (Samples: {len(fox.train_texts)})"
                print(msg); speech.say("Verstanden. Ich habe es gelernt.")
            except Exception as e:
                msg = f"Fox: Nutzung: correct: <label>  oder  correct: <text> => <label>. Fehler: {e}"
                print(msg); speech.say("Fehler bei der Korrektur.")
            continue

        # === Fakten speichern (knowledge.db) ===
        if l.startswith("merke:"):
            try:
                payload = user.split("merke:", 1)[1]
                key, val = [p.strip() for p in payload.split("=", 1)]
                norm_key = key.strip().lower()
                set_fact(norm_key, val)
                print(f"Fox: Gemerkt – {norm_key} = {val}.")
                speech.say("Okay, gemerkt.")
            except Exception:
                msg = "Fox: Nutzung: merke: <frage> = <antwort>"
                print(msg); speech.say("Fehler bei 'merke'.")
            continue

        # === Normaler Dialog (Tastatur) ===
        process_input(fox, speech, user)


if __name__ == "__main__":
    main()
