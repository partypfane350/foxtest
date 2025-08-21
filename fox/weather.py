# fox/weather.py
import os
import requests
from urllib.parse import quote_plus

API_KEY = os.getenv("OPENWEATHER_KEY", "2b118b7ee7e7b7812a41049225055d22")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

def _clean(s: str) -> str:
    return " ".join((s or "").strip().split())

def get_weather(city_or_query: str) -> str:
    """
    Holt Wetter NUR, wenn man es explizit aufruft. Robust gegen Groß/Klein & Spaces.
    Erwartet eine Stadt (am besten aus DB), probiert aber Varianten durch.
    """
    q = _clean(city_or_query)
    if not q:
        return "Kein Ort angegeben."

    tried = set()
    candidates = [q, q.title()]
    last = None
    for cand in candidates:
        if not cand or cand.lower() in tried:
            continue
        tried.add(cand.lower())
        try:
            url = f"{BASE_URL}?q={quote_plus(cand)}&appid={API_KEY}&units=metric&lang=de"
            r = requests.get(url, timeout=7)
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
            if r.status_code == 404:
                continue  # nächste Variante probieren
            try:
                msg = r.json().get("message", "")
            except Exception:
                msg = ""
            return f"Wetter-Fehler {r.status_code}: {msg or 'unbekannt'}"
        except Exception as e:
            last = f"Fehler beim Wetterabruf: {e}"
    return last or f"Wetter für '{q}' nicht gefunden."
