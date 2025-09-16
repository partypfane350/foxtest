import os
import sys
import sqlite3
import csv
import zipfile
from pyrosm import OSM


DB_PATH = os.path.join("geo_data", "geo.db")
SRC_DIR = os.path.join("geo_data", "src")
OSM_DIR = os.path.join("geo_data", "osm")


BATCH_SIZE = 5000
PROGRESS_STEP = 20000


def connect_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA synchronous = NORMAL;")
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def create_schema(con):
    cur = con.cursor()

    # timezones
    cur.execute("""
    CREATE TABLE IF NOT EXISTS timezones (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tz_name TEXT UNIQUE NOT NULL,
      utc_offset REAL,
      notes TEXT
    )
    """)

    # continents
    cur.execute("""
    CREATE TABLE IF NOT EXISTS continents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL,
      population INTEGER,
      area_km2 REAL,
      country_count INTEGER
    )
    """)

    # countries
    cur.execute("""
    CREATE TABLE IF NOT EXISTS countries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      iso2 TEXT UNIQUE,
      iso3 TEXT,
      name TEXT NOT NULL,
      capital TEXT,
      population INTEGER,
      area_km2 REAL,
      continent_id INTEGER REFERENCES continents(id) ON DELETE SET NULL,
      languages TEXT,
      currency TEXT,
      tz_id INTEGER REFERENCES timezones(id) ON DELETE SET NULL,
      latitude REAL,
      longitude REAL
    )
    """)

    # cities
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      geonameid INTEGER UNIQUE,
      name TEXT NOT NULL,
      ascii_name TEXT,
      country_id INTEGER REFERENCES countries(id) ON DELETE CASCADE,
      admin1 TEXT,
      population INTEGER,
      area_km2 REAL,
      latitude REAL,
      longitude REAL,
      tz_id INTEGER REFERENCES timezones(id) ON DELETE SET NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS streets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      street_name TEXT NOT NULL,
      house_number TEXT,
      city_id INTEGER REFERENCES cities(id) ON DELETE CASCADE,
      postalcode TEXT,
      country_id INTEGER REFERENCES countries(id) ON DELETE CASCADE,
      latitude REAL,
      longitude REAL
    )
    """)


    # mountains
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mountains (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      geonameid INTEGER UNIQUE,
      name TEXT NOT NULL,
      country_id INTEGER REFERENCES countries(id) ON DELETE SET NULL,
      admin1 TEXT,
      latitude REAL,
      longitude REAL,
      elevation INTEGER,
      tz_id INTEGER REFERENCES timezones(id) ON DELETE SET NULL,
      notes TEXT
    )
    """)

    # rivers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rivers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      geonameid INTEGER UNIQUE,
      name TEXT NOT NULL,
      country_id INTEGER REFERENCES countries(id) ON DELETE SET NULL,
      latitude REAL,
      longitude REAL,
      tz_id INTEGER REFERENCES timezones(id) ON DELETE SET NULL,
      notes TEXT
    )
    """)

    # lakes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lakes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      geonameid INTEGER UNIQUE,
      name TEXT NOT NULL,
      country_id INTEGER REFERENCES countries(id) ON DELETE SET NULL,
      area_km2 REAL,
      latitude REAL,
      longitude REAL,
      tz_id INTEGER REFERENCES timezones(id) ON DELETE SET NULL,
      notes TEXT
    )
    """)

    # seas
    cur.execute("""
    CREATE TABLE IF NOT EXISTS seas (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      geonameid INTEGER UNIQUE,
      name TEXT NOT NULL,
      area_km2 REAL,
      latitude REAL,
      longitude REAL,
      notes TEXT
    )
    """)

    # oceans
    cur.execute("""
    CREATE TABLE IF NOT EXISTS oceans (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      geonameid INTEGER UNIQUE,
      name TEXT NOT NULL,
      area_km2 REAL,
      latitude REAL,
      longitude REAL,
      notes TEXT
    )
    """)

    # alt_names
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alt_names (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      target_table TEXT NOT NULL,
      target_geonameid INTEGER,
      lang TEXT,
      name TEXT,
      is_preferred INTEGER DEFAULT 0
    )
    """)

    con.commit()


def import_timezones(con):
    tz_file = os.path.join(SRC_DIR, "timeZones.txt")
    if not os.path.exists(tz_file):
        print("timeZones.txt fehlt, überspringe.")
        return

    cur = con.cursor()
    with open(tz_file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)  # header
        batch = []
        for row in reader:
            if len(row) < 3:
                continue
            tz_name = row[1]
            gmt_offset = row[2]
            batch.append((tz_name, gmt_offset, None))
            if len(batch) >= BATCH_SIZE:
                cur.executemany(
                    "INSERT OR IGNORE INTO timezones (tz_name, utc_offset, notes) VALUES (?, ?, ?)", batch
                )
                con.commit()
                batch.clear()
        if batch:
            cur.executemany(
                "INSERT OR IGNORE INTO timezones (tz_name, utc_offset, notes) VALUES (?, ?, ?)", batch
            )
            con.commit()
    print("✓ timezones importiert")


def import_countries_and_continents(con):
    file = os.path.join(SRC_DIR, "countryInfo.txt")
    if not os.path.exists(file):
        print("countryInfo.txt fehlt, überspringe.")
        return

    cur = con.cursor()
    continents = {}
    with open(file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 15 or row[0].startswith("#"):
                continue
            iso2 = row[0]
            iso3 = row[1]
            name = row[4]
            capital = row[5]
            area = row[6] or None
            pop = row[7] or None
            continent = row[8]
            currency = row[10]
            languages = row[15] if len(row) > 15 else None

            cur.execute("INSERT OR IGNORE INTO continents (name) VALUES (?)", (continent,))
            cur.execute("SELECT id FROM continents WHERE name=?", (continent,))
            cont_id = cur.fetchone()[0]

            cur.execute("""
              INSERT OR IGNORE INTO countries
              (iso2, iso3, name, capital, population, area_km2, continent_id, languages, currency)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (iso2, iso3, name, capital, pop, area, cont_id, languages, currency))

            continents.setdefault(cont_id, {"pop": 0, "area": 0, "count": 0})
            try:
                continents[cont_id]["pop"] += int(pop)
            except:
                pass
            try:
                continents[cont_id]["area"] += float(area)
            except:
                pass
            continents[cont_id]["count"] += 1

    for cid, vals in continents.items():
        cur.execute("UPDATE continents SET population=?, area_km2=?, country_count=? WHERE id=?",
                    (vals["pop"], vals["area"], vals["count"], cid))

    con.commit()
    print("✓ countries & continents importiert")


def import_allcountries(con):
    file = os.path.join(SRC_DIR, "allCountries.zip")
    if not os.path.exists(file):
        print("allCountries.zip fehlt, überspringe.")
        return

    cur = con.cursor()
    with zipfile.ZipFile(file) as zf:
        with zf.open("allCountries.txt") as f:
            reader = (line.decode("utf-8") for line in f)
            batch_city, batch_mtn, batch_riv, batch_lake, batch_sea, batch_ocean = [], [], [], [], [], []
            for i, line in enumerate(reader, 1):
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 10:
                    continue

                geonameid = int(parts[0])
                name = parts[1]
                asciiname = parts[2]
                lat, lon = parts[4], parts[5]
                fc = parts[6]  # feature class
                fcode = parts[7]
                cc = parts[8]
                admin1 = parts[10]
                pop = parts[14] or None
                tz = parts[17] if len(parts) > 17 else None
                elev = parts[15] if len(parts) > 15 else None

                if fc == "P":  # city
                    batch_city.append((geonameid, name, asciiname, cc, admin1, pop, None, lat, lon, tz))
                elif fc == "T":  # mountains
                    batch_mtn.append((geonameid, name, cc, admin1, lat, lon, elev, tz, None))
                elif fc == "H":
                    if fcode.startswith("STM"):
                        batch_riv.append((geonameid, name, cc, lat, lon, tz, None))
                    elif fcode.startswith("LK"):
                        batch_lake.append((geonameid, name, cc, None, lat, lon, tz, None))
                    elif fcode == "SEA":
                        batch_sea.append((geonameid, name, None, lat, lon, None))
                    elif fcode == "OCN":
                        batch_ocean.append((geonameid, name, None, lat, lon, None))

                if i % PROGRESS_STEP == 0:
                    print(f"... {i} Zeilen gelesen")
                if len(batch_city) >= BATCH_SIZE:
                    cur.executemany("""INSERT OR IGNORE INTO cities
                        (geonameid, name, ascii_name, country_id, admin1, population, area_km2, latitude, longitude, tz_id)
                        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL)""", batch_city)
                    batch_city.clear()
                if len(batch_mtn) >= BATCH_SIZE:
                    cur.executemany("""INSERT OR IGNORE INTO mountains
                        (geonameid, name, country_id, admin1, latitude, longitude, elevation, tz_id, notes)
                        VALUES (?, ?, NULL, ?, ?, ?, ?, NULL, ?)""", batch_mtn)
                    batch_mtn.clear()

            con.commit()
    print("✓ allCountries importiert (cities, mountains, rivers, lakes, seas, oceans)")


def import_altnames(con):
    file = os.path.join(SRC_DIR, "alternateNamesV2.zip")
    if not os.path.exists(file):
        print("alternateNamesV2.zip fehlt, überspringe.")
        return

    cur = con.cursor()
    with zipfile.ZipFile(file) as zf:
        with zf.open("alternateNamesV2.txt") as f:
            batch = []
            for i, line in enumerate(f, 1):
                parts = line.decode("utf-8").strip().split("\t")
                if len(parts) < 4:
                    continue
                geonameid = parts[1]
                lang = parts[2]
                name = parts[3]
                is_pref = parts[4] if len(parts) > 4 else "0"
                batch.append(("generic", geonameid, lang, name, is_pref))
                if len(batch) >= BATCH_SIZE:
                    cur.executemany("""INSERT INTO alt_names
                        (target_table, target_geonameid, lang, name, is_preferred)
                        VALUES (?, ?, ?, ?, ?)""", batch)
                    con.commit()
                    batch.clear()
            if batch:
                cur.executemany("""INSERT INTO alt_names
                    (target_table, target_geonameid, lang, name, is_preferred)
                    VALUES (?, ?, ?, ?, ?)""", batch)
                con.commit()
    print("✓ alt_names importiert")


def import_osm_streets(con):
    """
    Importiert Straßen aus OSM für alle Länder in die streets-Tabelle
    """
    cur = con.cursor()
    # Alle Länder abrufen
    cur.execute("""
        SELECT iso2, id FROM countries
        WHERE iso2 IS NOT NULL
    """)
    countries = cur.fetchall()

    for iso2, country_id in countries:
        iso2_lower = iso2.lower()
        pbf_file = os.path.join(OSM_DIR, f"{iso2_lower}-latest.osm.pbf")
        
        if not os.path.exists(pbf_file):
            print(f"⚠ {iso2} PBF nicht gefunden ({pbf_file}), überspringe.")
            continue
        
        print(f"\n🌍 Importiere Straßen für {iso2}")
        osm = OSM(pbf_file)
        streets = osm.get_data_by_custom_criteria(custom_filter={"highway": True})

        if streets.empty:
            print(f"⚠ Keine Straßen für {iso2} gefunden, überspringe.")
            continue

        streets = streets.rename(columns={
            "name": "street_name",
            "housenumber": "house_number",
            "postcode": "postalcode",
            "city": "city_id",           
            "lat": "latitude",
            "lon": "longitude"
        })
        
        streets["country_id"] = country_id
        streets = streets[["street_name", "house_number", "postalcode", "city_id", "country_id", "latitude", "longitude"]]

        streets.to_sql("streets", con, if_exists="append", index=False)
        print(f"✅ Straßen für {iso2} importiert")

def main():
    con = connect_db()
    create_schema(con)
    import_timezones(con)
    import_countries_and_continents(con)
    import_allcountries(con)
    import_altnames(con)
    import_osm_streets(con)
    con.close()
    print("✅ Import abgeschlossen.")

if __name__ == "__main__":
    main()