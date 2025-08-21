from __future__ import annotations
import sqlite3
import re
import unicodedata
from contextlib import closing
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

# === Config ===
DB_PATH = (Path(__file__).resolve().parents[1] / "geo_data" / "geo.db").as_posix()

# Optional ISO2 fallback (used only if iso2 table missing)
ISO2 = {
    "DE": "Deutschland","FR":"Frankreich","CH":"Schweiz","IT":"Italien","ES":"Spanien",
    "AT":"Österreich","US":"USA","GB":"Vereinigtes Königreich","JP":"Japan","CN":"China",
    "IN":"Indien","BR":"Brasilien","CA":"Kanada","AU":"Australien"
}

# === Regex for free-text place hints ===
_LOC_PAT = re.compile(r"\b(?:in|über|zu|nach|für)\s+([A-Za-zÄÖÜäöüß\-’']+)\b", re.IGNORECASE)
_WHERE_IS_PAT = re.compile(r"\b(?:wo\s+ist|where\s+is)\s+([A-Za-zÄÖÜäöüß\-’']+)\b", re.IGNORECASE)

# ---------- Utilities ----------
def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).casefold()
    return "".join(c for c in s if not unicodedata.combining(c))

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-zÄÖÜäöüß\-’']+", text)

# ---------- DB helpers ----------
class _Schema:
    table: str
    name_col: str
    country_code_col: Optional[str]
    country_name_col: Optional[str]
    population_col: Optional[str]
    lat_col: Optional[str]
    lon_col: Optional[str]
    iso_table: Optional[str]
    iso_code_col: Optional[str]
    iso_name_col: Optional[str]

    def __init__(self):
        self.table = "places"
        self.name_col = "name"
        self.country_code_col = "country_code"
        self.country_name_col = None
        self.population_col = "population"
        self.lat_col = "lat"
        self.lon_col = "lon"
        self.iso_table = "iso2"
        self.iso_code_col = "code"
        self.iso_name_col = "name"

def _open():
    return sqlite3.connect(DB_PATH)

def _table_columns(cur, table: str) -> List[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]

# Create minimal schema if DB is empty (no crash on first run)
def ensure_geo_db(seed_minimal: bool = True) -> None:
    with closing(_open()) as conn, closing(conn.cursor()) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS places (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              country_code TEXT,
              country TEXT,
              population INTEGER,
              lat REAL,
              lon REAL
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS iso2 (
              code TEXT PRIMARY KEY,
              name TEXT NOT NULL
            );
            """
        )
        if seed_minimal:
            cur.execute("SELECT COUNT(*) FROM places;")
            if (cur.fetchone() or [0])[0] == 0:
                cur.executemany(
                    "INSERT INTO places (name, country_code, country, population, lat, lon) VALUES (?,?,?,?,?,?)",
                    [
                        ("Bern","CH","Schweiz",133883,46.94809,7.44744),
                        ("Zürich","CH","Schweiz",402762,47.37689,8.54169),
                        ("Basel","CH","Schweiz",178247,47.55960,7.58858),
                        ("Berlin","DE","Deutschland",3769495,52.52001,13.40495),
                    ]
                )
            cur.execute("SELECT COUNT(*) FROM iso2;")
            if (cur.fetchone() or [0])[0] == 0:
                cur.executemany(
                    "INSERT INTO iso2 (code, name) VALUES (?,?)",
                    [(k,v) for k,v in ISO2.items()]
                )
        conn.commit()

# Flexible schema detection (places/cities)
def _detect_schema(cur) -> _Schema:
    s = _Schema()
    found_table = None
    for t in ("places", "cities"):
        try:
            cols = _table_columns(cur, t)
            if cols:
                found_table = t; break
        except sqlite3.Error:
            pass
    if not found_table:
        # Initialize minimal schema and use places
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS places (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              country_code TEXT,
              country TEXT,
              population INTEGER,
              lat REAL,
              lon REAL
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);")
        found_table = "places"

    s.table = found_table
    cols = set(_table_columns(cur, found_table))

    s.name_col = "name" if "name" in cols else ("city" if "city" in cols else "name")
    s.country_code_col = "country_code" if "country_code" in cols else ("iso2" if "iso2" in cols else None)
    s.country_name_col = "country" if "country" in cols else None

    s.population_col = None
    for cand in ("population","pop","inhabitants"):
        if cand in cols:
            s.population_col = cand; break

    s.lat_col = "lat" if "lat" in cols else ("latitude" if "latitude" in cols else None)
    s.lon_col = "lon" if "lon" in cols else ("longitude" if "longitude" in cols else None)

    try:
        iso_cols = set(_table_columns(cur, "iso2"))
        if iso_cols:
            s.iso_table = "iso2"
            s.iso_code_col = "code" if "code" in iso_cols else None
            s.iso_name_col = "name" if "name" in iso_cols else None
        else:
            s.iso_table = None
    except sqlite3.Error:
        s.iso_table = None

    return s

# Country name resolver (code → name)
def _country_name_from_code(cur, code: Optional[str], schema: _Schema) -> Optional[str]:
    if not code:
        return None
    if not schema.iso_table or not schema.iso_code_col or not schema.iso_name_col:
        return ISO2.get(code)
    try:
        cur.execute(
            f"SELECT {schema.iso_name_col} FROM {schema.iso_table} WHERE {schema.iso_code_col} = ?",
            (code,)
        )
        row = cur.fetchone()
        return row[0] if row else ISO2.get(code)
    except sqlite3.Error:
        return ISO2.get(code)

# Row → dict

def _row_to_place_dict(row: Tuple, cols: List[str], schema: _Schema, cur) -> Dict[str, Any]:
    data = dict(zip(cols, row))
    name = data.get(schema.name_col)
    country_name = data.get(schema.country_name_col)
    if not country_name and schema.country_code_col and data.get(schema.country_code_col):
        country_name = _country_name_from_code(cur, data.get(schema.country_code_col), schema)

    return {
        "type": "place",
        "name": name,
        "country": country_name or data.get(schema.country_code_col),
        "population": data.get(schema.population_col) if schema.population_col else None,
        "lat": data.get(schema.lat_col) if schema.lat_col else None,
        "lon": data.get(schema.lon_col) if schema.lon_col else None,
    }

# Public search APIs

def search_places(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    if not query:
        return []
    like = f"%{query}%"
    with closing(_open()) as conn, closing(conn.cursor()) as cur:
        schema = _detect_schema(cur)
        cols = _table_columns(cur, schema.table)
        select_cols = ", ".join(cols)
        # Order by population if available
        if schema.population_col:
            cur.execute(
                f"SELECT {select_cols} FROM {schema.table} WHERE {schema.name_col} LIKE ? ORDER BY {schema.population_col} DESC",
                (like,)
            )
        else:
            cur.execute(
                f"SELECT {select_cols} FROM {schema.table} WHERE {schema.name_col} LIKE ?",
                (like,)
            )
        rows = cur.fetchall()
        results = [_row_to_place_dict(r, cols, schema, cur) for r in rows]
        return results[:limit]


def best_match(query: str) -> Optional[Dict[str, Any]]:
    candidates = search_places(query, limit=10)
    if not candidates:
        return None
    qn = _normalize(query)
    # exact normalized match first
    for c in candidates:
        if _normalize(c["name"]) == qn:
            return c
    # else take highest population if present
    with_pop = [c for c in candidates if c.get("population") is not None]
    if with_pop:
        return max(with_pop, key=lambda x: x["population"])
    return candidates[0]

# Countries via iso2 table (name search)

def search_country_by_name(query: str) -> Optional[Dict[str, Any]]:
    if not query:
        return None
    like = f"%{query}%"
    with closing(_open()) as conn, closing(conn.cursor()) as cur:
        try:
            cur.execute("SELECT name, code FROM iso2 WHERE name LIKE ? COLLATE NOCASE", (like,))
            row = cur.fetchone()
            if row:
                name, code = row
                return {"type":"country","name": name, "country": name, "iso2": code,
                        "population": None, "lat": None, "lon": None}
        except sqlite3.Error:
            return None
    return None

# Unified free-text resolver

def _guess_place_query(text: str, ctx: Dict[str, Any] | None = None) -> Optional[str]:
    if not text:
        return None
    if isinstance(ctx, dict):
        slots = ctx.get("slots") or {}
        if isinstance(slots, dict) and slots.get("where"):
            w = str(slots["where"]).strip()
            if w:
                return w
    m = _LOC_PAT.search(text)
    if m:
        return m.group(1).strip()
    m2 = _WHERE_IS_PAT.search(text)
    if m2:
        return m2.group(1).strip()
    tokens = _tokenize(text)
    if tokens:
        return tokens[-1].strip()
    return None


def resolve_place(text: str, ctx: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    q = _guess_place_query(text, ctx)
    if not q:
        return None
    q = q[:1].upper() + q[1:]
    try:
        place = best_match(q)
        if place:
            return place
    except Exception:
        pass
    # try country lookup
    return search_country_by_name(q)

# Speaking geo-skill (kept for Q&A)

def geo_skill(text: str, ctx: Dict[str, Any] | None = None) -> str:
    place = resolve_place(text, ctx)
    if not place:
        return "Sag mir einen Ort, z. B. 'Infos über Zürich'."
    if place.get("type") == "country":
        return f"{place['name']} (Land) – nenn mir eine Stadt darin, z. B. Hauptstadt."
    name = place.get("name") or "Unbekannt"
    country = place.get("country") or "–"
    pop = place.get("population")
    lat = place.get("lat"); lon = place.get("lon")
    parts = [f"{name} – {country}"]
    if pop is not None:
        parts.append(f"Einwohner: {pop:,}".replace(",","."))
    if isinstance(lat,(int,float)) and isinstance(lon,(int,float)):
        parts.append(f"Koordinaten: {lat:.4f}, {lon:.4f}")
    return " | ".join(parts)