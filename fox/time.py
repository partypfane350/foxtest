# fox/time.py
from __future__ import annotations
import os
from datetime import datetime

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# Standard-Zeitzone (per Env überschreibbar)
TIMEZONE = os.getenv("FOX_TZ", "Europe/Zurich")

def _get_timezone():
    """
    Reihenfolge:
    1) zoneinfo (wenn tzdata verfügbar)
    2) dateutil.gettz (wenn installiert)
    3) Fallback: None -> Systemzeit
    """
    if ZoneInfo:
        try:
            return ZoneInfo(TIMEZONE)
        except Exception:
            pass
    try:
        from dateutil.tz import gettz
        tz = gettz(TIMEZONE)
        if tz:
            return tz
    except Exception:
        pass
    return None

def now_dt():
    tz = _get_timezone()
    return datetime.now(tz) if tz else datetime.now()

def time_skill(text: str, ctx: dict | None = None) -> str:
    """
    Gibt die aktuelle Uhrzeit; falls 'datum' oder 'tag' im Text vorkommt, auch Datum/Wochentag.
    """
    t = (text or "").lower()
    now = now_dt()
    if "datum" in t or "tag" in t:
        return f"Heute ist {now:%A, %d.%m.%Y} – es ist {now:%H:%M}"
    return f"Es ist gerade {now:%H:%M}"
