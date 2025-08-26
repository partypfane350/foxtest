from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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

# ---------- App + Middleware ----------

app = FastAPI(title="CrownFox Local API", version="1.1.0", description="Lokale REST-API für Fox")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # für lokale Tests ok
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/chat", response_class=HTMLResponse)
def chat_page():
    return """
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CrownFox Chat</title>
<style>
  :root { --bg:#0b0f14; --fg:#e6eef7; --muted:#9fb3c8; --card:#121922; --accent:#4cc9f0; }
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,Segoe UI,Roboto,Arial}
  .wrap{max-width:820px;margin:0 auto;padding:16px}
  .chat{background:var(--card);border-radius:16px;padding:12px;height:70vh;overflow:auto;box-shadow:0 6px 24px rgba(0,0,0,.35)}
  .msg{display:flex;gap:10px;margin:12px 0}
  .me .bubble{background:#1f2a36}
  .bot .bubble{background:#14202b;border-left:3px solid var(--accent)}
  .bubble{padding:10px 12px;border-radius:12px;max-width:75%;white-space:pre-wrap}
  .meta{color:var(--muted);font-size:12px;margin-top:2px}
  form{display:flex;gap:8px;margin-top:12px}
  input{flex:1;padding:12px;border-radius:12px;border:1px solid #233243;background:#0e141b;color:var(--fg)}
  button{padding:12px 16px;border:0;border-radius:12px;background:var(--accent);color:#052436;font-weight:600;cursor:pointer}
  button[disabled]{opacity:.6;cursor:not-allowed}
</style>
</head>
<body>
  <div class="wrap">
    <h2>🦊 CrownFox – Lokaler Chat</h2>
    <div id="chat" class="chat" aria-live="polite"></div>
    <form id="form" autocomplete="off">
      <input id="inp" placeholder="Schreib deine Nachricht…" autofocus />
      <button id="send" type="submit">Senden</button>
    </form>
    <div class="meta" id="meta">Verbunden mit /handle</div>
  </div>
<script>
const chat = document.getElementById('chat');
const form = document.getElementById('form');
const inp  = document.getElementById('inp');
const meta = document.getElementById('meta');
function addMsg(role, text){
  const row = document.createElement('div');
  row.className = 'msg ' + (role==='user'?'me':'bot');
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}
async function askFox(text){
  const res = await fetch('/handle', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({text})
  });
  if(!res.ok){
    const t = await res.text();
    throw new Error('HTTP '+res.status+': '+t);
  }
  const data = await res.json();
  return data.reply || '';
}
form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const text = inp.value.trim();
  if(!text) return;
  addMsg('user', text);
  inp.value = ''; inp.focus();
  form.querySelector('button').disabled = true;
  try{
    const reply = await askFox(text);
    addMsg('bot', reply);
  }catch(err){
    addMsg('bot', 'Fehler: '+err.message);
  }finally{
    form.querySelector('button').disabled = false;
  }
});
addMsg('bot','Hallo! Ich bin lokal bereit. Frag mich etwas – z. B. „wie spät ist es?“');
</script>
</body>
</html>
    """

# Start:
# .\.venv\Scripts\activate
# uvicorn server:app --host 127.0.0.1 --port 8010 --reload
