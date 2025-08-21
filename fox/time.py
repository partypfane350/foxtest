from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Standard seit Python 3.9
except ImportError:
    ZoneInfo = None

from dateutil.tz import gettz  

TIMEZONE = "Europe/Zurich"


def _get_timezone():
    # 1) Versuche zoneinfo
    if ZoneInfo:
        try:
            return ZoneInfo(TIMEZONE)
        except Exception:
            pass

    # 2) Fallback mit dateutil
    tz = gettz(TIMEZONE)
    if tz:
        return tz

    # 3) Als letztes: None (Systemzeit)
    return None


def time_skill(text: str, ctx=None) -> str:
    tz = _get_timezone()
    now = datetime.now(tz) if tz else datetime.now()

    # kleine Logik: falls User nach Datum fragt
    text_lower = text.lower()
    if "datum" in text_lower or "tag" in text_lower:
        return f"Heute ist {now:%A, %d.%m.%Y} und die Uhrzeit ist {now:%H:%M}"
    return f"Es ist gerade {now:%H:%M}"