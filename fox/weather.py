import os
import requests
from urllib.parse import quote_plus

API_KEY = os.getenv("OPENWEATHER_KEY", "2b118b7ee7e7b7812a41049225055d22")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

def _clean(text: str) -> str:
    return " ".join((text or "").strip().split())

def get_weather(city: str) -> str:
    city = _clean(city)
    if not city:
        return "Kein Ort angegeben."

    candidates = []
    seen = set()
    for cand in (city, city.title()):
        if cand and cand.lower() not in seen:
            seen.add(cand.lower())
            candidates.append(cand)

    last_err = None
    for cand in candidates:
        try:
            url = f"{BASE_URL}?q={quote_plus(cand)}&appid={API_KEY}&units=metric&lang=de"
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                data = r.json()
                name = data.get("name", cand)
                main = data.get("main", {})
                wx   = (data.get("weather") or [{}])[0]
                temp = main.get("temp")
                desc = wx.get("description", "keine Beschreibung")
                if temp is None:
                    return f"Wetterdaten für {name} unvollständig."
                return f"Wetter in {name}: {temp:.1f}°C, {desc}"
            elif r.status_code == 404:
                last_err = f"Wetter für '{cand}' nicht gefunden."
                continue
            else:
                try:
                    msg = r.json().get("message", "")
                except Exception:
                    msg = ""
                return f"Wetter-Fehler {r.status_code}: {msg or 'unbekannt'}"
        except Exception as e:
            last_err = f"Fehler beim Wetterabruf: {e}"
    return last_err or f"Wetter für '{city}' nicht gefunden."