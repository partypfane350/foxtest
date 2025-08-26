from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# === Knowledge DB ===
from fox.knowledge import init_db, set_fact, get_fact, search_facts
init_db()

# Deine Fox-Logik wiederverwenden
from main import FoxAssistant, IntentModel, labels, MODEL_PATH

app = FastAPI(title="CrownFox Local API", version="1.1.0", description="Lokale REST-API für Fox")

# Singleton-Instanz (einmal starten)
fox = FoxAssistant()

# ---------- Schemas ----------
class HandleReq(BaseModel):
    text: str

class LearnReq(BaseModel):
    question: str
    label: str

class FactReq(BaseModel):
    key: str
    value: str

class TerminReq(BaseModel):
    text: str  # frei: "morgen 16:00 Zahnarzt"

class KnowledgeSetReq(BaseModel):
    key: str
    value: str

# ---------- Helpers ----------
def ok(msg: str, **extra):
    return {"ok": True, "msg": msg, **extra}

# ---------- Routes ----------
@app.get("/")
def root():
    return {
        "name": "CrownFox",
        "version": "1.1.0",
        "labels": labels.CLASSES,
        "model_meta": fox.model.meta,
        "conf_threshold": 0.60
    }

@app.post("/handle")
def handle(req: HandleReq):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text darf nicht leer sein")
    reply = fox.handle(text)
    return {"ok": True, "reply": reply}

@app.post("/learn")
def learn(req: LearnReq):
    try:
        fox.learn_pair(req.question, req.label)   # speichert + snapshot("learn")
        return ok(f"gelernt: '{req.question}' => {req.label}", samples=len(fox.train_texts))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---- Altes JSON-Facts (Kompatibilität) ----
@app.post("/fact")
def fact(req: FactReq):
    from main import FACTS_PATH, load_json, save_json
    facts = load_json(FACTS_PATH, {})
    facts[req.key] = req.value
    save_json(FACTS_PATH, facts)
    return ok(f"gemerkt: {req.key}={req.value}", count=len(facts))

# ---- Neues Knowledge (SQLite) ----
@app.post("/knowledge/set")
def knowledge_set(req: KnowledgeSetReq):
    set_fact(req.key, req.value)
    return ok(f"knowledge gesetzt: {req.key}")

@app.get("/knowledge/get")
def knowledge_get(key: str):
    val = get_fact(key)
    if val is None:
        raise HTTPException(status_code=404, detail="key nicht gefunden")
    return {"ok": True, "key": key, "value": val}

@app.get("/knowledge/search")
def knowledge_search(q: str):
    rows = search_facts(q)
    return {"ok": True, "hits": [{"key": k, "value": v} for (k, v) in rows]}

@app.post("/termin")
def termin(req: TerminReq):
    reply = fox.termin(req.text, ctx={})
    return {"ok": True, "reply": reply}

@app.get("/memory")
def memory():
    return {"ok": True, "memory": list(fox.memory)}

@app.post("/save")
def save():
    fox.save_all()
    fox.snapshot(tag="save")  # manueller Snapshot
    return ok(f"modell + trainingsdaten gespeichert → {MODEL_PATH}")

@app.post("/reload")
def reload_model():
    fox.model = IntentModel.load(MODEL_PATH)
    return ok("modell neu geladen")

# Optional: Audio ein/aus schalten (Platzhalter)
@app.post("/audio/{mode}")
def audio_toggle(mode: str):
    if mode not in ("an", "aus"):
        raise HTTPException(status_code=400, detail="nutze 'an' oder 'aus'")
    return ok(f"audio {mode} (endpoint vorhanden; instanzverw. optional)")

# Start:
# .\.venv\Scripts\activate
# uvicorn server:app --host 127.0.0.1 --port 8010 --reload
