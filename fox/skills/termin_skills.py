# fox/_skills/termin.py
from __future__ import annotations
import re, json
from pathlib import Path
from typing import Optional, Dict
from fox.labels import WEEKDAYS  # nutzt deine bestehende Liste

# Speicherort wie in main – Projekt-Root/calendar.json
CALENDAR_PATH = Path(__file__).resolve().parents[2] / "calendar.json"

def _load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default

def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _extract_datetime(text: str) -> Dict[str, Optional[str]]:
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

def termin_skill(text: str, ctx: dict | None = None) -> str:
    dt = _extract_datetime(text)
    if not dt["when"] and not dt["time"]:
        return "Für den Termin brauche ich Datum/Zeit (z. B. 'morgen 15:00')."

    evts = _load_json(CALENDAR_PATH, [])
    evts.append({"text": text, "when": dt["when"], "time": dt["time"]})
    _save_json(CALENDAR_PATH, evts)

    parts = [p for p in [dt["when"], dt["time"]] if p]
    return f"Okay, Termin gespeichert: {' '.join(parts)}".strip()

def list_termine() -> str:
    evts = _load_json(CALENDAR_PATH, [])
    if not evts:
        return "Keine Termine gefunden."
    lines = []
    for i, evt in enumerate(evts, 1):
        parts = [p for p in [evt.get("when"), evt.get("time")] if p]
        lines.append(f"{i}. {' '.join(parts)} - {evt.get('text', '')}".strip())
    return "Deine Termine:\n" + "\n".join(lines)    
