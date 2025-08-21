import sqlite3 
from pathlib import Path
import re
from typing import List, Dict, Optional

DB_PATH = (Path(__file__).resolve().parents[1] / "geo_data" / "geo.db").as_posix()

ISO2 = {
    "DE": "Deutschland","FR":"Frankreich","CH":"Schweiz","IT":"Italien","ES":"Spanien",
    "AT":"Österreich","US":"USA","GB":"Vereinigtes Königreich","JP":"Japan","CN":"China",
    "IN":"Indien","BR":"Brasilien","CA":"Kanada","AU":"Australien"
}

def _open():
    return sqlite3.connect(DB_PATH)

def search_places(query: str, limit: int = 5) -> List[Dict]:
    """Suche Orte per Name (case-insensitive), sortiert nach Bevölkerung."""
    if query is None:
        return []
    query = str(query).strip()
    if not query:
        return []

    con = _open()
    cur = con.cursor()
    cur.execute(
        """
        SELECT name, country_code, population, latitude, longitude, feature_class, feature_code
        FROM places
        WHERE LOWER(name) LIKE LOWER(?)
        ORDER BY population DESC
        LIMIT ?
        """,
        (f"%{query}%", int(limit))
    )
    rows = cur.fetchall()
    con.close()

    out: List[Dict] = []
    for (name, cc, pop, lat, lon, fclass, fcode) in rows:
        out.append({
            "name": name,
            "country_code": cc,
            "country": ISO2.get(cc, cc),
            "population": int(pop) if pop is not None else None,
            "lat": float(lat) if lat is not None else None,
            "lon": float(lon) if lon is not None else None,
            "feature_class": fclass,
            "feature_code": fcode,
        })
    return out

def best_match(query: str) -> Optional[Dict]:
    if not query:
        return None
    res = search_places(query, limit=1)
    return res[0] if res else None

_LOC_PAT = re.compile(r"\b(?:in|über|zu|nach|für)\s+([A-Za-zÄÖÜäöüß\-’']+)", re.IGNORECASE)
_WHERE_IS_PAT = re.compile(r"\bwo\s+ist\s+([A-Za-zÄÖÜäöüß\-’']+)", re.IGNORECASE)
def extract_location_inline(text: str) -> Optional[str]:
    m = _LOC_PAT.search(text)
    return m.group(1) if m else None

def geo_skill(text: str, ctx: dict) -> str:
    where = None
    if isinstance(ctx, dict):
        where = (ctx.get("slots") or {}).get("where")

    # 1) Standard: "in/über/..." <Ort>
    if not where:
        m = _LOC_PAT.search(text)
        if m:
            where = m.group(1)

    # 2) Neu: "wo ist <Ort>"
    if not where:
        m2 = _WHERE_IS_PAT.search(text)
        if m2:
            where = m2.group(1)

    # 3) Fallback: nimm das letzte Wort als Ort (z.B. "wo ist bern")
    if not where:
        tokens = re.findall(r"[A-Za-zÄÖÜäöüß\-’']+", text)
        if tokens:
            where = tokens[-1]

    if not where:
        return "Sag mir einen Ort, z. B. 'Infos über Zürich'."

    # hübsch normalisieren (Bern, New York, São Paulo …)
    where = where.strip()
    where = where[:1].upper() + where[1:]  # minimal normalisieren

    hit = best_match(where)
    if not hit:
        return f"Keine Infos zu '{where}' gefunden."

    name = hit["name"]; land = hit["country"]; pop = hit["population"]
    lat, lon = hit["lat"], hit["lon"]; fcode = hit["feature_code"] or "?"
    feat = {
        "PPLC":"Hauptstadt","PPLA":"Verwaltungssitz","PPLA2":"Verwaltungssitz (Stufe 2)",
        "PPLA3":"Verwaltungssitz (Stufe 3)","PPLA4":"Verwaltungssitz (Stufe 4)",
        "PPL":"bewohnter Ort","ADM1":"Region/Bundesland","ADM2":"Bezirk/Kreis"
    }.get(fcode, fcode)

    parts = [f"{name} – {land}"]
    if feat: parts.append(f"({feat})")
    if pop:  parts.append(f"Einwohner: {pop:,}".replace(",", "."))
    if lat is not None and lon is not None:
        parts.append(f"Koordinaten: {lat:.4f}, {lon:.4f}")
    return " | ".join(parts)
