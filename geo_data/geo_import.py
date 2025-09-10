from __future__ import annotations
import os, time, csv, zipfile
from pathlib import Path

# --- SQLite mit FTS5 (dein Python hat es i. d. R. schon; Fallback nur falls nötig) ---
try:
    import sqlite3
except Exception:  # pragma: no cover
    import pysqlite3 as sqlite3  # pip install pysqlite3-binary  (meist NICHT nötig)
    import sys
    sys.modules["sqlite3"] = sqlite3

# ========= Pfade robust bestimmen =========
BASE = Path(__file__).resolve().parent
# Wenn Script in geo_data/ liegt, gibt es ein ./src nebenan; sonst im Projekt-Root.
if (BASE / "src").exists():
    SRC = BASE / "src"
    DB  = BASE / "geo.db"
else:
    SRC = BASE / "geo_data" / "src"
    DB  = BASE / "geo_data" / "geo.db"

# ========= Konfiguration (per ENV überschreibbar) =========
# Welche Feature-KLASSEN (GeoNames fclass) importieren?  A,H,L,P,R,S
KEEP_FCLASS = set(os.getenv("KEEP_FCLASS", "A,H,L,P,R,S").split(","))

# Optional: nur bestimmte Feature-CODES (GeoNames fcode) behalten; leer = alle Codes der Klassen
KEEP_FCODES = set(filter(None, os.getenv("KEEP_FCODES", "").split(",")))

# Mindest-Einwohner für fclass=P (0 = alle Orte)
MIN_POP     = int(os.getenv("MIN_POP", "1000"))

# Alternativnamen-Sprachen
LANG_FILTER = set(os.getenv(
    "ALT_LANGS",
    "de,en,fr,it,es,ru,zh,ar,pt,tr,pl"
).split(","))

# PLZ-Deduplizierung: pro (Land, PLZ) eine Zeile
DEDUP_POSTAL = os.getenv("DEDUP_POSTAL", "1") != "0"

# FTS nur für diese Klassen (klein & schnell) — Standard: A & P
FTS_FCLASS = set(os.getenv("FTS_FCLASS", "A,P").split(","))


# ========= DB-Helfer =========
def open_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    con.execute("PRAGMA page_size=32768;")
    con.execute("PRAGMA cache_size=-400000;")
    return con


def create_schema(con: sqlite3.Connection):
    cur = con.cursor()
    # Stammdaten
    cur.execute("""CREATE TABLE IF NOT EXISTS countries(
        iso2 TEXT PRIMARY KEY, iso3 TEXT, name TEXT, capital TEXT,
        continent TEXT, population INTEGER, area_km2 REAL, currency TEXT,
        languages TEXT, tld TEXT, geoname_id INTEGER
    )""")

    # Admin-Codes
    cur.execute("""CREATE TABLE IF NOT EXISTS admin1(
        code TEXT PRIMARY KEY, name TEXT, name_ascii TEXT, geoname_id INTEGER, country_code TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin2(
        code TEXT PRIMARY KEY, name TEXT, name_ascii TEXT, geoname_id INTEGER, country_code TEXT
    )""")

    # Orte/Features
    cur.execute("""CREATE TABLE IF NOT EXISTS places(
        geonameid INTEGER PRIMARY KEY,
        name TEXT, ascii TEXT, country_code TEXT,
        admin1 TEXT, admin2 TEXT, admin3 TEXT, admin4 TEXT,
        fclass TEXT, fcode TEXT, lat REAL, lon REAL,
        population INTEGER, elevation INTEGER, dem INTEGER,
        timezone TEXT, moddate TEXT
    )""")

    # Alternativnamen
    cur.execute("""CREATE TABLE IF NOT EXISTS alt_names(
        geonameid INTEGER, lang TEXT, name TEXT, is_pref INTEGER, is_short INTEGER
    )""")

    # Postleitzahlen
    cur.execute("""CREATE TABLE IF NOT EXISTS postal(
        country_code TEXT, postcode TEXT, place TEXT,
        admin1 TEXT, admin1_code TEXT, admin2 TEXT, admin2_code TEXT,
        admin3 TEXT, admin3_code TEXT, lat REAL, lon REAL, accuracy INTEGER
    )""")

    # FTS-Tabellen (optional, falls FTS5 fehlt → überspringen wir in build_fts)
    try:
        cur.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS fts_place USING fts5(
            name, ascii, alt, country, content=''
        )""")
        cur.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS fts_postal USING fts5(
            place, postcode, admin1, admin2, admin3, country, content=''
        )""")
    except sqlite3.OperationalError as e:
        print(">> Hinweis: FTS5 nicht verfügbar – nutze LIKE/Indizes als Fallback. (", e, ")")

    con.commit()


# ========= Loader =========
def load_country_info(con: sqlite3.Connection, path: Path):
    print(">> countries …")
    cur = con.cursor()
    cur.execute("DELETE FROM countries")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            iso2, iso3, name, capital = p[0], p[1], p[4], p[5]
            try: area = float(p[6]) if p[6] else None
            except: area = None
            try: pop = int(p[7]) if p[7] else None
            except: pop = None
            cont, tld, curr, langs = p[8], p[10], p[11], p[15]
            try: gid = int(p[16]) if len(p) > 16 and p[16] else None
            except: gid = None
            cur.execute("""INSERT OR REPLACE INTO countries
                (iso2,iso3,name,capital,continent,population,area_km2,currency,languages,tld,geoname_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (iso2, iso3, name, capital, cont, pop, area, curr, langs, tld, gid))
    con.commit()


def load_admin_codes(con: sqlite3.Connection, admin1_path: Path, admin2_path: Path):
    print(">> admin1/admin2 …")
    cur = con.cursor()
    cur.execute("DELETE FROM admin1")
    cur.execute("DELETE FROM admin2")

    # admin1CodesASCII.txt
    with admin1_path.open("r", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 4: continue
            code, name, name_ascii, gid = p[0], p[1], p[2], p[3]
            country = code.split(".")[0]
            cur.execute("INSERT OR REPLACE INTO admin1(code,name,name_ascii,geoname_id,country_code) VALUES(?,?,?,?,?)",
                        (code, name, name_ascii, int(gid), country))

    # admin2Codes.txt
    with admin2_path.open("r", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 4: continue
            code, name, name_ascii, gid = p[0], p[1], p[2], p[3]
            country = code.split(".")[0]
            cur.execute("INSERT OR REPLACE INTO admin2(code,name,name_ascii,geoname_id,country_code) VALUES(?,?,?,?,?)",
                        (code, name, name_ascii, int(gid), country))

    con.commit()


def load_places(con: sqlite3.Connection, zip_path: Path):
    print(f">> places aus {zip_path.name} (KLASSEN={','.join(sorted(KEEP_FCLASS))}, MIN_POP={MIN_POP}, FCODES={','.join(sorted(KEEP_FCODES)) or 'ALLE'}) …")
    cur = con.cursor()
    cur.execute("DELETE FROM places")
    zf = zipfile.ZipFile(zip_path, "r")
    name = [n for n in zf.namelist() if n.endswith("allCountries.txt")][0]
    with zf.open(name) as f:
        rdr = csv.reader((line.decode("utf-8") for line in f), delimiter="\t")
        batch = []
        def commit():
            if not batch: return
            cur.executemany("""INSERT OR REPLACE INTO places
                (geonameid,name,ascii,country_code,admin1,admin2,admin3,admin4,
                 fclass,fcode,lat,lon,population,elevation,dem,timezone,moddate)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)
            con.commit(); batch.clear()

        for row in rdr:
            if len(row) < 19: 
                continue
            try:
                geonameid = int(row[0]); name = row[1]; asciiname = row[2]
                lat = float(row[4]); lon = float(row[5])
                fclass = row[6]; fcode = row[7]; cc = row[8]
                admin1, admin2, admin3, admin4 = row[10], row[11], row[12], row[13]
                pop = int(row[14]) if row[14] else 0
                elev = int(row[15]) if row[15] else None
                dem  = int(row[16]) if row[16] else None
                tz   = row[17]; mod  = row[18]
            except Exception:
                continue

            # Filter: Klassen
            if fclass not in KEEP_FCLASS:
                continue

            # Filter: Codes (falls gesetzt)
            if KEEP_FCODES and fcode not in KEEP_FCODES:
                continue

            # Mindestpopulation nur für P
            if fclass == "P" and MIN_POP and pop < MIN_POP:
                continue

            batch.append((geonameid,name,asciiname,cc,admin1,admin2,admin3,admin4,
                          fclass,fcode,lat,lon,pop,elev,dem,tz,mod))
            if len(batch) >= 20000:
                commit()
        commit()
    zf.close()


def load_alt_names(con: sqlite3.Connection, zip_path: Path):
    print(">> alt_names (Sprachen: " + ",".join(sorted(LANG_FILTER)) + ") …")
    cur = con.cursor()
    cur.execute("DELETE FROM alt_names")
    zf = zipfile.ZipFile(zip_path, "r")
    name = [n for n in zf.namelist() if n.endswith("alternateNamesV2.txt")][0]
    with zf.open(name) as f:
        rdr = csv.reader((line.decode("utf-8", "ignore") for line in f), delimiter="\t")
        batch = []
        def commit():
            if not batch: return
            cur.executemany("""INSERT INTO alt_names
                (geonameid,lang,name,is_pref,is_short) VALUES(?,?,?,?,?)""", batch)
            con.commit(); batch.clear()

        for row in rdr:
            if len(row) < 5: 
                continue
            try:
                geonameid = int(row[1])
            except:
                continue
            lang = (row[2] or "").split(",")[0].lower()
            if lang not in LANG_FILTER:
                continue
            alt  = row[3]
            is_pref = 1 if (len(row) > 4 and row[4] == "1") else 0
            is_short= 1 if (len(row) > 5 and row[5] == "1") else 0
            batch.append((geonameid, lang, alt, is_pref, is_short))
            if len(batch) >= 50000:
                commit()
        commit()
    zf.close()


def load_postal(con: sqlite3.Connection, zip_path: Path):
    print(f">> postal aus {zip_path.name} …")
    cur = con.cursor()
    cur.execute("DELETE FROM postal")
    zf = zipfile.ZipFile(zip_path, "r")
    name = [n for n in zf.namelist() if n.endswith("allCountries.txt")][0]
    with zf.open(name) as f:
        rdr = csv.reader((line.decode("utf-8", "ignore") for line in f), delimiter="\t")
        batch = []
        def commit():
            if not batch: return
            cur.executemany("""INSERT INTO postal
                (country_code,postcode,place,admin1,admin1_code,admin2,admin2_code,
                 admin3,admin3_code,lat,lon,accuracy)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", batch)
            con.commit(); batch.clear()

        for row in rdr:
            if len(row) < 12:
                continue
            cc, pc, pl = row[0], row[1], row[2]
            a1, a1c, a2, a2c, a3, a3c = row[3], row[4], row[5], row[6], row[7], row[8]
            try:  lat = float(row[9]);  lon = float(row[10])
            except: lat = None; lon = None
            try:  acc = int(row[11]) if row[11] else None
            except: acc = None
            batch.append((cc,pc,pl,a1,a1c,a2,a2c,a3,a3c,lat,lon,acc))
            if len(batch) >= 50000:
                commit()
        commit()
    zf.close()

    if DEDUP_POSTAL:
        print(">> postal dedup (1 Zeile pro (country, postcode)) …")
        cur.execute("""
            CREATE TEMP TABLE _dedup AS
            SELECT MIN(rowid) AS rowid
            FROM postal
            GROUP BY country_code, postcode
        """)
        cur.execute("""
            CREATE TABLE postal2 AS
            SELECT p.* FROM postal p JOIN _dedup d ON p.rowid = d.rowid
        """)
        cur.execute("DROP TABLE postal")
        cur.execute("ALTER TABLE postal2 RENAME TO postal")
        con.commit()


# ========= FTS & Indizes =========
def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name=?", (name,))
    return cur.fetchone() is not None


def build_fts(con: sqlite3.Connection):
    print(">> FTS & Indizes …")
    cur = con.cursor()

    # Prüfe, ob FTS-Tabellen existieren (sonst Fallback)
    fts_place_ok  = _table_exists(con, "fts_place")
    fts_postal_ok = _table_exists(con, "fts_postal")

    if fts_place_ok:
        cur.execute("DELETE FROM fts_place")
        placeholders = ",".join("?" for _ in FTS_FCLASS) or "?"
        cur.execute(f"""
            INSERT INTO fts_place(rowid, name, ascii, alt, country)
            SELECT p.rowid, p.name, p.ascii,
                   COALESCE((SELECT group_concat(a.name, ' ')
                             FROM alt_names a WHERE a.geonameid=p.geonameid),''),
                   COALESCE((SELECT c.name FROM countries c WHERE c.iso2=p.country_code), p.country_code)
            FROM places p
            WHERE p.fclass IN ({placeholders})
        """, tuple(FTS_FCLASS))
    else:
        print(">> Hinweis: fts_place fehlt → LIKE-Fallback (Suche langsamer).")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_places_name ON places(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_places_ascii ON places(ascii)")

    if fts_postal_ok:
        cur.execute("DELETE FROM fts_postal")
        cur.execute("""
            INSERT INTO fts_postal(rowid, place, postcode, admin1, admin2, admin3, country)
            SELECT rowid, place, postcode,
                   COALESCE(admin1,''), COALESCE(admin2,''), COALESCE(admin3,''), country_code
            FROM postal
        """)
    else:
        print(">> Hinweis: fts_postal fehlt → LIKE-Fallback für PLZ.")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_postal_code ON postal(country_code, postcode)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_postal_place ON postal(place)")

    # Generelle Indizes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_places_cc  ON places(country_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_places_pop ON places(population)")
    con.commit()


# ========= MAIN =========
def main():
    t0 = time.time()
    # Pflichtdateien vorhanden?
    need = [
        SRC / "countryInfo.txt",
        SRC / "admin1CodesASCII.txt",
        SRC / "admin2Codes.txt",
        SRC / "allCountries.zip",        # PLACES
        SRC / "alternateNamesV2.zip",
    ]
    missing = [str(p) for p in need if not p.exists()]
    if missing:
        raise FileNotFoundError("Fehlende Dateien in geo_data/src: " + ", ".join(missing))

    con = open_db()
    try:
        create_schema(con)
        load_country_info(con, SRC / "countryInfo.txt")
        load_admin_codes(con, SRC / "admin1CodesASCII.txt", SRC / "admin2Codes.txt")
        load_places(con, SRC / "allCountries.zip")
        load_alt_names(con, SRC / "alternateNamesV2.zip")

        # PLZ optional
        POSTAL = SRC / "postal" / "allCountries.zip"
        if POSTAL.exists():
            load_postal(con, POSTAL)

        build_fts(con)
        con.execute("VACUUM")
    finally:
        con.close()

    print(
        f"OK: {DB} gebaut in {time.time()-t0:.1f}s | "
        f"KLASSEN={','.join(sorted(KEEP_FCLASS))} | "
        f"FCODES={','.join(sorted(KEEP_FCODES)) or 'ALLE'} | "
        f"MIN_POP={MIN_POP} | FTS_KLASSEN={','.join(sorted(FTS_FCLASS))}"
    )


if __name__ == "__main__":
    main()
