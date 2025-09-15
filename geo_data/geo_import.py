from __future__ import annotations
import os, time, csv, zipfile, argparse
from pathlib import Path

# --- SQLite with FTS5 fallback ---
try:
    import sqlite3
except Exception:  # pragma: no cover
    import pysqlite3 as sqlite3
    import sys
    sys.modules["sqlite3"] = sqlite3

# ======== Paths ========
BASE = Path(__file__).resolve().parent
if (BASE / "src").exists():
    SRC = BASE / "src"
    DB  = BASE / "geo.db"
else:
    SRC = BASE / "geo_data" / "src"
    DB  = BASE / "geo_data" / "geo.db"

# ======== CLI / Config ========
parser = argparse.ArgumentParser(description="Memory-friendly GeoNames import into SQLite")
parser.add_argument("--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "5000")),
                    help="Number of rows per executemany commit (default 5000)")
parser.add_argument("--progress-step", type=int, default=int(os.getenv("PROGRESS_STEP", "20000")),
                    help="Print progress every N inserted rows")
parser.add_argument("--min-pop", type=int, default=int(os.getenv("MIN_POP", "1000")),
                    help="Minimum population for class P (default 1000)")
parser.add_argument("--no-vacuum", action="store_true", help="Skip VACUUM at the end (safer/fast)")
parser.add_argument("--temp-file", action="store_true", help="Force temp_store=FILE (recommended)")
args = parser.parse_args()

# ======== Behavior flags (can also be set via ENV in original script) ========
KEEP_FCLASS = set(os.getenv("KEEP_FCLASS", "A,H,L,P,R,S").split(","))
KEEP_FCODES = set(filter(None, os.getenv("KEEP_FCODES", "").split(",")))
LANG_FILTER = set(os.getenv("ALT_LANGS", "de,en,fr,it,es,ru,zh,ar,pt,tr,pl").split(","))
DEDUP_POSTAL = os.getenv("DEDUP_POSTAL", "1") != "0"
FTS_FCLASS = set(os.getenv("FTS_FCLASS", "A,P").split(","))
MIN_POP = args.min_pop
BATCH_SIZE = args.batch_size
PROGRESS_STEP = args.progress_step

# ======== DB helpers ========

def open_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    # prefer FILE if requested (safer on low-RAM systems)
    if args.temp_file:
        cur.execute("PRAGMA temp_store=FILE;")
    else:
        # default to FILE for safety even if not requested
        cur.execute("PRAGMA temp_store=FILE;")
    # moderate cache size (positive value = number of pages; use small negative for KB if desired)
    cur.execute("PRAGMA page_size=32768;")
    # smaller cache to avoid large memory reservation
    cur.execute("PRAGMA cache_size=20000;")
    con.commit()
    return con


def create_schema(con: sqlite3.Connection):
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS countries(
        iso2 TEXT PRIMARY KEY, iso3 TEXT, name TEXT, capital TEXT,
        continent TEXT, population INTEGER, area_km2 REAL, currency TEXT,
        languages TEXT, tld TEXT, geoname_id INTEGER
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS admin1(
        code TEXT PRIMARY KEY, name TEXT, name_ascii TEXT, geoname_id INTEGER, country_code TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin2(
        code TEXT PRIMARY KEY, name TEXT, name_ascii TEXT, geoname_id INTEGER, country_code TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS places(
        geonameid INTEGER PRIMARY KEY,
        name TEXT, ascii TEXT, country_code TEXT,
        admin1 TEXT, admin2 TEXT, admin3 TEXT, admin4 TEXT,
        fclass TEXT, fcode TEXT, lat REAL, lon REAL,
        population INTEGER, elevation INTEGER, dem INTEGER,
        timezone TEXT, moddate TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS alt_names(
        geonameid INTEGER, lang TEXT, name TEXT, is_pref INTEGER, is_short INTEGER
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS postal(
        country_code TEXT, postcode TEXT, place TEXT,
        admin1 TEXT, admin1_code TEXT, admin2 TEXT, admin2_code TEXT,
        admin3 TEXT, admin3_code TEXT, lat REAL, lon REAL, accuracy INTEGER
    )""")

    # Try creating FTS tables; if not available we fallback to indexes later
    try:
        cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_place USING fts5(name, ascii, alt, country, content='')")
        cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_postal USING fts5(place, postcode, admin1, admin2, admin3, country, content='')")
    except sqlite3.OperationalError:
        print('>> Hinweis: FTS5 nicht verfügbar – Fallback wird genutzt')

    con.commit()

# ======== Loaders (memory-friendly) ========

def load_country_info(con: sqlite3.Connection, path: Path):
    print('>> countries ...')
    cur = con.cursor()
    cur.execute('DELETE FROM countries')
    con.commit()
    with path.open('r', encoding='utf-8') as f:
        batch = []
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            p = line.rstrip('\n').split('\t')
            iso2, iso3, name, capital = p[0], p[1], p[4], p[5]
            try: area = float(p[6]) if p[6] else None
            except: area = None
            try: pop = int(p[7]) if p[7] else None
            except: pop = None
            cont, tld, curr, langs = p[8], p[10], p[11], p[15]
            try: gid = int(p[16]) if len(p) > 16 and p[16] else None
            except: gid = None
            batch.append((iso2, iso3, name, capital, cont, pop, area, curr, langs, tld, gid))
            if len(batch) >= BATCH_SIZE:
                cur.executemany('INSERT OR REPLACE INTO countries (iso2,iso3,name,capital,continent,population,area_km2,currency,languages,tld,geoname_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)', batch)
                con.commit(); batch.clear()
        if batch:
            cur.executemany('INSERT OR REPLACE INTO countries (iso2,iso3,name,capital,continent,population,area_km2,currency,languages,tld,geoname_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)', batch)
            con.commit()


def load_admin_codes(con: sqlite3.Connection, admin1_path: Path, admin2_path: Path):
    print('>> admin1/admin2 ...')
    cur = con.cursor()
    cur.execute('DELETE FROM admin1')
    cur.execute('DELETE FROM admin2')
    con.commit()

    def commit_batch(batch, sql):
        if not batch: return
        cur.executemany(sql, batch); con.commit(); batch.clear()

    batch = []
    with admin1_path.open('r', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) < 4: continue
            code, name, name_ascii, gid = p[0], p[1], p[2], p[3]
            country = code.split('.')[0]
            batch.append((code, name, name_ascii, int(gid), country))
            if len(batch) >= BATCH_SIZE:
                commit_batch(batch, 'INSERT OR REPLACE INTO admin1(code,name,name_ascii,geoname_id,country_code) VALUES(?,?,?,?,?)')
    if batch: commit_batch(batch, 'INSERT OR REPLACE INTO admin1(code,name,name_ascii,geoname_id,country_code) VALUES(?,?,?,?,?)')

    batch = []
    with admin2_path.open('r', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) < 4: continue
            code, name, name_ascii, gid = p[0], p[1], p[2], p[3]
            country = code.split('.')[0]
            batch.append((code, name, name_ascii, int(gid), country))
            if len(batch) >= BATCH_SIZE:
                commit_batch(batch, 'INSERT OR REPLACE INTO admin2(code,name,name_ascii,geoname_id,country_code) VALUES(?,?,?,?,?)')
    if batch: commit_batch(batch, 'INSERT OR REPLACE INTO admin2(code,name,name_ascii,geoname_id,country_code) VALUES(?,?,?,?,?)')


def load_places(con: sqlite3.Connection, zip_path: Path):
    print(f">> places aus {zip_path.name} (KLASSEN={','.join(sorted(KEEP_FCLASS))}, MIN_POP={MIN_POP}, FCODES={','.join(sorted(KEEP_FCODES)) or 'ALLE'}) ...")
    cur = con.cursor()
    cur.execute('DELETE FROM places')
    con.commit()

    zf = zipfile.ZipFile(zip_path, 'r')
    name = [n for n in zf.namelist() if n.endswith('allCountries.txt')][0]
    inserted = 0

    with zf.open(name) as f:
        rdr = csv.reader((line.decode('utf-8', 'ignore') for line in f), delimiter='\t')
        batch = []
        for row in rdr:
            if len(row) < 19: continue
            try:
                geonameid = int(row[0]); pname = row[1]; asciiname = row[2]
                lat = float(row[4]); lon = float(row[5])
                fclass = row[6]; fcode = row[7]; cc = row[8]
                admin1, admin2, admin3, admin4 = row[10], row[11], row[12], row[13]
                pop = int(row[14]) if row[14] else 0
                elev = int(row[15]) if row[15] else None
                dem  = int(row[16]) if row[16] else None
                tz   = row[17]; mod  = row[18]
            except Exception:
                continue

            if fclass not in KEEP_FCLASS:
                continue
            if KEEP_FCODES and fcode not in KEEP_FCODES:
                continue
            if fclass == 'P' and MIN_POP and pop < MIN_POP:
                continue

            batch.append((geonameid,pname,asciiname,cc,admin1,admin2,admin3,admin4,
                          fclass,fcode,lat,lon,pop,elev,dem,tz,mod))
            if len(batch) >= BATCH_SIZE:
                cur.executemany('''INSERT OR REPLACE INTO places
                    (geonameid,name,ascii,country_code,admin1,admin2,admin3,admin4,
                     fclass,fcode,lat,lon,population,elevation,dem,timezone,moddate)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', batch)
                con.commit()
                inserted += len(batch)
                batch.clear()
                if inserted % PROGRESS_STEP == 0:
                    print(f"... {inserted:,} Zeilen importiert".replace(',', '.'))
        if batch:
            cur.executemany('''INSERT OR REPLACE INTO places
                (geonameid,name,ascii,country_code,admin1,admin2,admin3,admin4,
                 fclass,fcode,lat,lon,population,elevation,dem,timezone,moddate)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', batch)
            con.commit()
            inserted += len(batch)
            batch.clear()
    zf.close()
    print(f"... insgesamt {inserted:,} Zeilen in places eingefügt".replace(',', '.'))


def load_alt_names(con: sqlite3.Connection, zip_path: Path):
    print('>> alt_names (Sprachen: ' + ','.join(sorted(LANG_FILTER)) + ') ...')
    cur = con.cursor()
    cur.execute('DELETE FROM alt_names')
    con.commit()

    zf = zipfile.ZipFile(zip_path, 'r')
    name = [n for n in zf.namelist() if n.endswith('alternateNamesV2.txt')][0]
    inserted = 0
    with zf.open(name) as f:
        rdr = csv.reader((line.decode('utf-8', 'ignore') for line in f), delimiter='\t')
        batch = []
        for row in rdr:
            if len(row) < 5: continue
            try:
                geonameid = int(row[1])
            except:
                continue
            lang = (row[2] or '').split(',')[0].lower()
            if lang not in LANG_FILTER: continue
            alt  = row[3]
            is_pref = 1 if (len(row) > 4 and row[4] == '1') else 0
            is_short= 1 if (len(row) > 5 and row[5] == '1') else 0
            batch.append((geonameid, lang, alt, is_pref, is_short))
            if len(batch) >= BATCH_SIZE:
                cur.executemany('INSERT INTO alt_names (geonameid,lang,name,is_pref,is_short) VALUES(?,?,?,?,?)', batch)
                con.commit(); inserted += len(batch); batch.clear()
        if batch:
            cur.executemany('INSERT INTO alt_names (geonameid,lang,name,is_pref,is_short) VALUES(?,?,?,?,?)', batch)
            con.commit(); inserted += len(batch); batch.clear()
    zf.close()
    print(f"... insgesamt {inserted:,} Einträge in alt_names".replace(',', '.'))


def load_postal(con: sqlite3.Connection, zip_path: Path):
    print(f">> postal aus {zip_path.name} ...")
    cur = con.cursor()
    cur.execute('DELETE FROM postal')
    con.commit()

    zf = zipfile.ZipFile(zip_path, 'r')
    name = [n for n in zf.namelist() if n.endswith('allCountries.txt')][0]
    inserted = 0
    with zf.open(name) as f:
        rdr = csv.reader((line.decode('utf-8', 'ignore') for line in f), delimiter='\t')
        batch = []
        for row in rdr:
            if len(row) < 12: continue
            cc, pc, pl = row[0], row[1], row[2]
            a1, a1c, a2, a2c, a3, a3c = row[3], row[4], row[5], row[6], row[7], row[8]
            try:  lat = float(row[9]);  lon = float(row[10])
            except: lat = None; lon = None
            try:  acc = int(row[11]) if row[11] else None
            except: acc = None
            batch.append((cc,pc,pl,a1,a1c,a2,a2c,a3,a3c,lat,lon,acc))
            if len(batch) >= BATCH_SIZE:
                cur.executemany('INSERT INTO postal (country_code,postcode,place,admin1,admin1_code,admin2,admin2_code,admin3,admin3_code,lat,lon,accuracy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', batch)
                con.commit(); inserted += len(batch); batch.clear()
        if batch:
            cur.executemany('INSERT INTO postal (country_code,postcode,place,admin1,admin1_code,admin2,admin2_code,admin3,admin3_code,lat,lon,accuracy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', batch)
            con.commit(); inserted += len(batch); batch.clear()
    zf.close()

    if DEDUP_POSTAL:
        print('>> postal dedup (1 Zeile pro (country, postcode)) ...')
        cur.execute('CREATE TEMP TABLE _dedup AS SELECT MIN(rowid) AS rowid FROM postal GROUP BY country_code, postcode')
        cur.execute('CREATE TABLE postal2 AS SELECT p.* FROM postal p JOIN _dedup d ON p.rowid = d.rowid')
        cur.execute('DROP TABLE postal')
        cur.execute('ALTER TABLE postal2 RENAME TO postal')
        con.commit()

    print(f"... insgesamt {inserted:,} PLZ-Einträge".replace(',', '.'))

# ======== FTS & Indizes (chunked to avoid large memory use) ========

def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name=?", (name,))
    return cur.fetchone() is not None


def build_fts(con: sqlite3.Connection):
    print('>> FTS & Indizes ...')
    cur = con.cursor()
    fts_place_ok  = _table_exists(con, 'fts_place')
    fts_postal_ok = _table_exists(con, 'fts_postal')

    # places -> fts_place: do in chunks
    if fts_place_ok:
        cur.execute('DELETE FROM fts_place')
        # iterate places in chunks
        offset = 0
        chunk = 50000
        while True:
            rows = list(cur.execute('SELECT rowid, name, ascii FROM places ORDER BY rowid LIMIT ? OFFSET ?', (chunk, offset)))
            if not rows: break
            insert_batch = []
            for row in rows:
                rowid, name, ascii = row
                # get alt names for this row (small subquery per row) - cheaper than building huge join
                alt = ' '.join([r[0] for r in cur.execute('SELECT name FROM alt_names WHERE geonameid=?', (rowid,))])
                country = cur.execute('SELECT name FROM countries WHERE iso2=(SELECT country_code FROM places WHERE rowid=?)', (rowid,)).fetchone()
                country = country[0] if country else None
                insert_batch.append((rowid, name or '', ascii or '', alt or '', country or ''))
                if len(insert_batch) >= 2000:
                    cur.executemany('INSERT INTO fts_place(rowid, name, ascii, alt, country) VALUES(?,?,?,?,?)', insert_batch)
                    con.commit(); insert_batch.clear()
            if insert_batch:
                cur.executemany('INSERT INTO fts_place(rowid, name, ascii, alt, country) VALUES(?,?,?,?,?)', insert_batch)
                con.commit(); insert_batch.clear()
            offset += chunk
        con.commit()
    else:
        print('>> Hinweis: fts_place fehlt -> CREATE INDEX fallback')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_places_name ON places(name)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_places_ascii ON places(ascii)')

    # postal -> fts_postal
    if fts_postal_ok:
        cur.execute('DELETE FROM fts_postal')
        # insert in chunks from postal
        offset = 0
        chunk = 50000
        while True:
            rows = list(cur.execute('SELECT rowid, place, postcode, admin1, admin2, admin3, country_code FROM postal ORDER BY rowid LIMIT ? OFFSET ?', (chunk, offset)))
            if not rows: break
            insert_batch = [(r[0], r[1] or '', r[2] or '', r[3] or '', r[4] or '', r[5] or '', r[6] or '') for r in rows]
            cur.executemany('INSERT INTO fts_postal(rowid, place, postcode, admin1, admin2, admin3, country) VALUES(?,?,?,?,?,?,?)', insert_batch)
            con.commit()
            offset += chunk
    else:
        print('>> Hinweis: fts_postal fehlt -> CREATE INDEX fallback')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_postal_code ON postal(country_code, postcode)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_postal_place ON postal(place)')

    # general indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_places_cc  ON places(country_code)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_places_pop ON places(population)')
    con.commit()

# ======== MAIN ========

def main():
    t0 = time.time()
    need = [
        SRC / 'countryInfo.txt',
        SRC / 'admin1CodesASCII.txt',
        SRC / 'admin2Codes.txt',
        SRC / 'allCountries.zip',
        SRC / 'alternateNamesV2.zip',
    ]
    missing = [str(p) for p in need if not p.exists()]
    if missing:
        raise FileNotFoundError('Fehlende Dateien in geo_data/src: ' + ', '.join(missing))

    con = open_db()
    try:
        create_schema(con)
        load_country_info(con, SRC / 'countryInfo.txt')
        load_admin_codes(con, SRC / 'admin1CodesASCII.txt', SRC / 'admin2Codes.txt')
        load_places(con, SRC / 'allCountries.zip')
        load_alt_names(con, SRC / 'alternateNamesV2.zip')

        POSTAL = SRC / 'postal' / 'allCountries.zip'
        if POSTAL.exists():
            load_postal(con, POSTAL)

        build_fts(con)

        if not args.no_vacuum:
            print('>> VACUUM ... (optional)')
            con.execute('VACUUM')
    finally:
        con.close()

    print(f"OK: {DB} gebaut in {time.time()-t0:.1f}s | KLASSEN={','.join(sorted(KEEP_FCLASS))} | FCODES={','.join(sorted(KEEP_FCODES)) or 'ALLE'} | MIN_POP={MIN_POP} | FTS_KLASSEN={','.join(sorted(FTS_FCLASS))}")

if __name__ == '__main__':
    main()
