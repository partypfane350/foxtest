import os
import sqlite3
import csv
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "geo.db")
SRC_DIR = os.path.join(BASE_DIR, "src")
OSM_DIR = os.path.join(BASE_DIR, "osm")

BATCH_SIZE = 5000

def connect_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA synchronous = NORMAL;")
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def create_schema(con):
    cur = con.cursor()

    # Zeitzonen
    cur.execute("""
    CREATE TABLE IF NOT EXISTS timezones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tz_name TEXT UNIQUE NOT NULL,
        utc_offset REAL,
        notes TEXT
    )""")

    # Kontinente
    cur.execute("""
    CREATE TABLE IF NOT EXISTS continents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        population INTEGER,
        area_km2 REAL,
        country_count INTEGER
    )""")

    # Länder
    cur.execute("""
    CREATE TABLE IF NOT EXISTS countries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        capital TEXT,
        population INTEGER,
        area_km2 REAL,
        currency TEXT,
        continent_id INTEGER REFERENCES continents(id),
        iso2 TEXT,
        iso3 TEXT,
        languages TEXT,
        latitude REAL,
        longitude REAL,
        tz_id INTEGER REFERENCES timezones(id)
    )""")

    # Städte
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        postalcode TEXT,
        population INTEGER,
        area_km2 REAL,
        languages TEXT,
        country_id INTEGER REFERENCES countries(id),
        latitude REAL,
        longitude REAL,
        tz_id INTEGER REFERENCES timezones(id)
    )""")

    # Postleitzahlen
    cur.execute("""
    CREATE TABLE IF NOT EXISTS postal_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country_id INTEGER REFERENCES countries(id),
        postalcode TEXT,
        place TEXT,
        admin1 TEXT,
        admin2 TEXT,
        latitude REAL,
        longitude REAL
    )""")

    # Berge
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mountains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        country_id INTEGER REFERENCES countries(id),
        latitude REAL,
        longitude REAL,
        elevation INTEGER
    )""")

    # Flüsse
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        country_id INTEGER REFERENCES countries(id),
        latitude REAL,
        longitude REAL
    )""")

    # Meere
    cur.execute("""
    CREATE TABLE IF NOT EXISTS seas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        area_km2 REAL,
        latitude REAL,
        longitude REAL
    )""")

    # Ozeane
    cur.execute("""
    CREATE TABLE IF NOT EXISTS oceans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        area_km2 REAL,
        latitude REAL,
        longitude REAL
    )""")

    con.commit()

def import_timezones(con):
    file = os.path.join(SRC_DIR, "timeZones.txt")
    if not os.path.exists(file):
        print("timeZones.txt fehlt, überspringe.")
        return
    cur = con.cursor()
    batch = []
    with open(file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            tz_name, offset = row[1], row[2]
            batch.append((tz_name, offset, None))
            if len(batch) >= BATCH_SIZE:
                cur.executemany(
                    "INSERT OR IGNORE INTO timezones (tz_name, utc_offset, notes) VALUES (?, ?, ?)",
                    batch
                )
                con.commit()
                batch.clear()
    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO timezones (tz_name, utc_offset, notes) VALUES (?, ?, ?)", batch
        )
    con.commit()
    print("✓ Zeitzonen importiert")

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
            iso2, iso3 = row[0], row[1]
            name, capital = row[4], row[5]
            area = float(row[6]) if row[6] else None
            pop = int(row[7]) if row[7] else None
            continent_name = row[8]
            currency = row[10]
            languages = row[15] if len(row) > 15 else None
            tz_name = row[17] if len(row) > 17 else None

            cur.execute("INSERT OR IGNORE INTO continents (name) VALUES (?)", (continent_name,))
            cur.execute("SELECT id FROM continents WHERE name=?", (continent_name,))
            cont_id = cur.fetchone()[0]

            tz_id = None
            if tz_name:
                cur.execute("SELECT id FROM timezones WHERE tz_name=?", (tz_name,))
                t = cur.fetchone()
                if t:
                    tz_id = t[0]

            cur.execute("""INSERT OR IGNORE INTO countries
                (name, capital, population, area_km2, currency, continent_id, iso2, iso3, languages, latitude, longitude, tz_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, capital, pop, area, currency, cont_id, iso2, iso3, languages, None, None, tz_id)
            )

            continents.setdefault(cont_id, {"pop": 0, "area": 0, "count": 0})
            if pop:
                continents[cont_id]["pop"] += pop
            if area:
                continents[cont_id]["area"] += area
            continents[cont_id]["count"] += 1

    for cid, vals in continents.items():
        cur.execute("UPDATE continents SET population=?, area_km2=?, country_count=? WHERE id=?",
                    (vals["pop"], vals["area"], vals["count"], cid))
    con.commit()
    print("✓ Länder & Kontinente importiert")

def import_cities(con):
    file = os.path.join(SRC_DIR, "allCountries.zip")
    if not os.path.exists(file):
        print("allCountries.zip fehlt, überspringe.")
        return
    cur = con.cursor()
    with zipfile.ZipFile(file) as zf:
        with zf.open("allCountries.txt") as f:
            batch = []
            for line in f:
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 18:
                    continue
                name = parts[1]
                postalcode = None
                population = int(parts[14]) if parts[14] else None
                lat, lon = float(parts[4]), float(parts[5])
                country_code = parts[8]
                tz_name = parts[17]

                cur.execute("SELECT id FROM countries WHERE iso2=?", (country_code,))
                c = cur.fetchone()
                if not c:
                    continue
                country_id = c[0]

                tz_id = None
                if tz_name:
                    cur.execute("SELECT id FROM timezones WHERE tz_name=?", (tz_name,))
                    t = cur.fetchone()
                    if t:
                        tz_id = t[0]

                batch.append((name, postalcode, population, None, None, country_id, lat, lon, tz_id))
                if len(batch) >= BATCH_SIZE:
                    cur.executemany("""INSERT OR IGNORE INTO cities
                        (name, postalcode, population, area_km2, languages, country_id, latitude, longitude, tz_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", batch)
                    con.commit()
                    batch.clear()
            if batch:
                cur.executemany("""INSERT OR IGNORE INTO cities
                    (name, postalcode, population, area_km2, languages, country_id, latitude, longitude, tz_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", batch)
    con.commit()
    print("✓ Städte importiert")

def import_postal_codes(con):
    file = os.path.join(SRC_DIR, "postal.zip")
    if not os.path.exists(file):
        print("postal.zip fehlt, überspringe.")
        return
    cur = con.cursor()
    with zipfile.ZipFile(file) as zf:
        with zf.open("allCountries.txt") as f:
            batch = []
            for line in f:
                parts = line.decode("utf-8").strip().split("\t")
                if len(parts) < 11:
                    continue
                country_code, postalcode, place = parts[0], parts[1], parts[2]
                admin1, admin2 = parts[3], parts[5]
                lat, lon = float(parts[9]), float(parts[10])

                cur.execute("SELECT id FROM countries WHERE iso2=?", (country_code,))
                c = cur.fetchone()
                if not c:
                    continue
                country_id = c[0]

                batch.append((country_id, postalcode, place, admin1, admin2, lat, lon))
                if len(batch) >= BATCH_SIZE:
                    cur.executemany("""INSERT OR IGNORE INTO postal_codes
                        (country_id, postalcode, place, admin1, admin2, latitude, longitude)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""", batch)
                    con.commit()
                    batch.clear()
            if batch:
                cur.executemany("""INSERT OR IGNORE INTO postal_codes
                    (country_id, postalcode, place, admin1, admin2, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", batch)
    con.commit()
    print("✓ Postleitzahlen importiert")

def import_mountains_rivers_seas_oceans(con):
    file = os.path.join(SRC_DIR, "allCountries.zip")
    if not os.path.exists(file):
        print("allCountries.zip fehlt, überspringe.")
        return
    cur = con.cursor()
    with zipfile.ZipFile(file) as zf:
        with zf.open("allCountries.txt") as f:
            for line in f:
                parts = line.decode("utf-8").split("\t")
                if len(parts) < 10:
                    continue
                name = parts[1]
                fclass, fcode = parts[6], parts[7]
                lat, lon = float(parts[4]), float(parts[5])
                country_code = parts[8]

                cur.execute("SELECT id FROM countries WHERE iso2=?", (country_code,))
                c = cur.fetchone()
                country_id = c[0] if c else None

                if fclass == "T" and fcode == "MT":  # Mountain
                    elevation = int(parts[15]) if len(parts) > 15 and parts[15].isdigit() else None
                    cur.execute("""INSERT OR IGNORE INTO mountains (name, country_id, latitude, longitude, elevation)
                                   VALUES (?, ?, ?, ?, ?)""",
                                (name, country_id, lat, lon, elevation))
                elif fclass == "H" and fcode == "STM":  # River/stream
                    cur.execute("""INSERT OR IGNORE INTO rivers (name, country_id, latitude, longitude)
                                   VALUES (?, ?, ?, ?)""",
                                (name, country_id, lat, lon))
                elif fclass == "H" and fcode == "SEA":
                    cur.execute("""INSERT OR IGNORE INTO seas (name, area_km2, latitude, longitude)
                                   VALUES (?, ?, ?, ?)""",
                                (name, None, lat, lon))
                elif fclass == "H" and fcode == "OCN":
                    cur.execute("""INSERT OR IGNORE INTO oceans (name, area_km2, latitude, longitude)
                                   VALUES (?, ?, ?, ?)""",
                                (name, None, lat, lon))
    con.commit()
    print("✓ Berge, Flüsse, Meere & Ozeane importiert")

def main():
    con = connect_db()
    create_schema(con)
    import_timezones(con)
    import_countries_and_continents(con)
    import_cities(con)
    import_postal_codes(con)
    import_mountains_rivers_seas_oceans(con)
    con.close()
    print("✅ Import abgeschlossen")

if __name__ == "__main__":
    main()
