from __future__ import annotations
import sqlite3
from pathlib import Path
from contextlib import closing
from typing import Optional, Dict, Any, List, Tuple
import re

# === Pfad zur produktiven DB (anpassen falls nötig) ===
# Erwartetes Schema:
#   places(
#     name TEXT, country_code TEXT, population INTEGER,
#     latitude REAL, longitude REAL, feature_class TEXT, feature_code TEXT, ...
#   )
#   iso2(code TEXT PRIMARY KEY, name TEXT)
DB_PATH = (Path(__file__).resolve().parents[1] / "geo_data" / "geo.db").as_posix()

# Fallback ISO2->Name (nur wenn iso2-Tabelle fehlt/leer ist)
ISO2_FALLBACK = {
    "DE": "Germany", "FR": "France", "CH": "Switzerland", "IT": "Italy", "ES": "Spain",
    "AT": "Austria", "US": "United States", "GB": "United Kingdom", "JP": "Japan",
    "CN": "China", "IN": "India", "BR": "Brazil", "CA": "Canada", "AU": "Australia",
}

# Basis-Synonyme Deutsch → Englisch/Code (optional erweiterbar)
COUNTRY_SYNONYMS = {
    "schweiz": ["switzerland", "ch"],
    "spanien": ["spain", "es"],
    "deutschland": ["germany", "de"],
    "österreich": ["austria", "at"],
    "frankreich": ["france", "fr"],
    "italien": ["italy", "it"],
    "vereinigtes königreich": ["united kingdom", "uk", "gb"],
    "großbritannien": ["united kingdom", "uk", "gb"],
    "usa": ["united states", "us", "usa"],
}

# ---------- interne Helfer ----------
def _open():
    con = sqlite3.connect(DB_PATH)
    # Performance- und Stabilitäts-PRAGMAs (ungefährlich)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    return con

def _country_name_from_code(cur: sqlite3.Cursor, code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    try:
        cur.execute("SELECT name FROM iso2 WHERE code = ? COLLATE NOCASE", (code,))
        row = cur.fetchone()
        return row[0] if row else ISO2_FALLBACK.get(str(code).upper())
    except Exception:
        return ISO2_FALLBACK.get(str(code).upper())

def _normalize(s: str) -> str:
    return (s or "").strip().lower()

# ---------- Public: Suche ----------
def search_places(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Liefert Orte (nur Top-N) – Case-insensitive. Erwartet Index auf places(name).
    """
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"

    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute(
            """
            SELECT name, country_code, population, latitude, longitude, feature_class, feature_code
            FROM places
            WHERE name LIKE ? COLLATE NOCASE
            ORDER BY population DESC NULLS LAST
            LIMIT ?
            """,
            (like, int(limit))
        )
        rows = cur.fetchall()

        out: List[Dict[str, Any]] = []
        for (name, cc, pop, lat, lon, fclass, fcode) in rows:
            country_name = _country_name_from_code(cur, cc) or cc
            out.append({
                "type": "place",
                "name": name,
                "country_code": cc,
                "country": country_name,
                "population": int(pop) if pop is not None else None,
                "lat": float(lat) if lat is not None else None,
                "lon": float(lon) if lon is not None else None,
                "feature_class": fclass,
                "feature_code": fcode,
            })
        return out

def best_match(query: str) -> Optional[Dict[str, Any]]:
    """Beste Übereinstimmung für Ortsnamen – exakter Normalisierungsvergleich, sonst größte Bevölkerung."""
    candidates = search_places(query, limit=10)
    if not candidates:
        return None
    qn = _normalize(query)
    for c in candidates:
        if _normalize(c["name"]) == qn:
            return c
    with_pop = [c for c in candidates if c.get("population") is not None]
    if with_pop:
        return max(with_pop, key=lambda x: x["population"])
    return candidates[0]

def search_country_by_name(query: str) -> Optional[Dict[str, Any]]:
    """
    Länder-Suche über iso2 (englischer Name + ISO2 + Synonyme).
    Gibt ein 'country'-Dict zurück (ohne Koordinaten).
    """
    q_raw = (query or "").strip()
    if not q_raw:
        return None
    q = q_raw.lower()

    with closing(_open()) as con, closing(con.cursor()) as cur:
        # Name (englisch)
        try:
            cur.execute("SELECT name, code FROM iso2 WHERE name LIKE ? COLLATE NOCASE LIMIT 1", (f"%{q_raw}%",))
            row = cur.fetchone()
            if row:
                name, code = row
                return {"type": "country", "name": name, "country": name, "iso2": code}
        except Exception:
            pass
        # ISO2-Code
        try:
            cur.execute("SELECT name, code FROM iso2 WHERE code = ? COLLATE NOCASE LIMIT 1", (q_raw.upper(),))
            row = cur.fetchone()
            if row:
                name, code = row
                return {"type": "country", "name": name, "country": name, "iso2": code}
        except Exception:
            pass
        # Synonyme (Deutsch → Englisch/Code)
        for syn in COUNTRY_SYNONYMS.get(q, []):
            try:
                cur.execute("SELECT name, code FROM iso2 WHERE name LIKE ? COLLATE NOCASE LIMIT 1", (f"%{syn}%",))
                row = cur.fetchone()
                if row:
                    name, code = row
                    return {"type": "country", "name": name, "country": name, "iso2": code}
            except Exception:
                pass
            try:
                cur.execute("SELECT name, code FROM iso2 WHERE code = ? COLLATE NOCASE LIMIT 1", (syn.upper(),))
                row = cur.fetchone()
                if row:
                    name, code = row
                    return {"type": "country", "name": name, "country": name, "iso2": code}
            except Exception:
                pass
    return None

# ---------- Parsing/Resolver für Texte (nur Geo – kein Wetter) ----------
_LOC_PAT = re.compile(r"\b(?:in|über|zu|nach|für)\s+([A-Za-zÄÖÜäöüß\-’']+)", re.IGNORECASE)
_WHERE_IS_PAT = re.compile(r"\b(?:wo\s+ist|where\s+is)\s+([A-Za-zÄÖÜäöüß\-’']+)", re.IGNORECASE)

def _guess_place_query(text: str) -> Optional[str]:
    if not text:
        return None
    m = _LOC_PAT.search(text)
    if m:
        return m.group(1)
    m2 = _WHERE_IS_PAT.search(text)
    if m2:
        return m2.group(1)
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß\-’']+", text)
    if tokens:
        return tokens[-1]
    return None

def resolve_place(text: str) -> Optional[Dict[str, Any]]:
    """
    Versucht zuerst 'places', dann 'iso2' (als country) – gibt entweder
    ein 'place'-Dict (mit lat/lon) oder ein 'country'-Dict zurück.
    """
    q = _guess_place_query(text) or (text or "").strip()
    if not q:
        return None
    hit = best_match(q)
    if hit:
        return hit
    return search_country_by_name(q)

# ---------- Ausgabe für Geo-Infos ----------
def format_place_info(place: Dict[str, Any]) -> str:
    if not place:
        return "Ich konnte den Ort nicht finden."
    if place.get("type") == "country":
        return f"{place['name']} (Land)."
    name = place.get("name", "Unbekannt")
    country = place.get("country") or place.get("country_code") or "–"
    pop = place.get("population")
    lat, lon = place.get("lat"), place.get("lon")
    parts = [f"{name} – {country}"]
    if pop is not None:
        parts.append(f"Einwohner: {pop:,}".replace(",", "."))
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        parts.append(f"Koordinaten: {lat:.4f}, {lon:.4f}")
    return " | ".join(parts)

def geo_skill(text: str, ctx: Dict[str, Any] | None = None) -> str:
    """Geo-Infos NUR auf Nachfrage: liefert beschreibenden Text – kein Wetter!"""
    place = resolve_place(text)
    if not place:
        return "Sag mir einen Ort, z. B. 'Infos über Zürich'."
    return format_place_info(place)
