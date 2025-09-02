# fox/skills/weather_skills.py
from __future__ import annotations
import os, requests
from typing import Optional
from dotenv import load_dotenv

# .env sicher laden (auch falls main es später lädt)
load_dotenv()

def _get_api_key() -> Optional[str]:
    """
    Holt den OpenWeather-Key aus der .env / Umgebung.
    Unterstützt mehrere Namen inkl. Tippfehler.
    """
    candidates = [
        "OPENWEATHER_API_KEY",
        "OPENWEATHER_KEY",
        "OPENWEATHERMAP_API_KEY",
        "OWM_KEY",
        "OPENWEAHTER_KEY",   
        "openweahter_key",  
    ]
    for name in candidates:
        val = os.getenv(name)
        if val:
            return val.strip()
    return None

def get_weather(place: str) -> str:
    """
    Holt aktuelles Wetter über OpenWeather (Current Weather Data).
    Erwartet einen Ortsnamen wie 'Bern' oder 'Zürich'.
    """
    q = (place or "").strip()
    if not q:
        return "Sag mir eine Stadt für Wetter (z. B. 'Wetter in Bern')."

    api_key = _get_api_key()
    if not api_key:
        return ("Kein OpenWeather-Key gefunden. Lege in deiner .env an z. B.:\n"
                "OPENWEATHER_API_KEY=DEIN_KEY")

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": q, "appid": api_key, "units": "metric", "lang": "de"}
        r = requests.get(url, params=params, timeout=6)
        if r.status_code == 401:
            return "OpenWeather-Key ist ungültig (401). Bitte Key in .env prüfen."
        if r.status_code == 404:
            return f"Ort nicht gefunden: {q}"
        r.raise_for_status()
        data = r.json()

        name   = data.get("name") or q
        sys    = data.get("sys") or {}
        country= sys.get("country") or ""
        main   = data.get("main") or {}
        wx     = (data.get("weather") or [{}])[0]
        wind   = data.get("wind") or {}

        desc   = wx.get("description", "").capitalize()
        temp   = main.get("temp")
        feels  = main.get("feels_like")
        hum    = main.get("humidity")
        ws     = wind.get("speed")

        parts = [f"Wetter für {name}: {desc}"]
        if temp is not None:  parts.append(f"Temperatur {round(temp)}°C")
        if hum  is not None:  parts.append(f"Luftfeuchtigkeit {hum}%")
        if ws   is not None:  parts.append(f"Windstärke etwa {round(ws)} meter pro sekunde")

        return " | ".join(parts)

    except requests.Timeout:
        return "OpenWeather: Zeitüberschreitung. Versuch es gleich nochmal."
    except Exception as e:
        return f"OpenWeather-Fehler: {e}"
