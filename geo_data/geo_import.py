import sqlite3

DB_PATH = "geo.db"
SRC_FILE = "allCountries.txt"   

def create_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS places (
        geonameid INTEGER PRIMARY KEY,
        name TEXT,
        asciiname TEXT,
        alternatenames TEXT,
        latitude REAL,
        longitude REAL,
        feature_class TEXT,
        feature_code TEXT,
        country_code TEXT,
        cc2 TEXT,
        admin1_code TEXT,
        admin2_code TEXT,
        admin3_code TEXT,
        admin4_code TEXT,
        population INTEGER,
        elevation TEXT,
        dem TEXT,
        timezone TEXT,
        modification_date TEXT
    )
    """)
    cur.execute("DELETE FROM places")  
    con.commit()
    return con

def import_file():
    con = create_db()
    cur = con.cursor()
    batch = []
    with open(SRC_FILE, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            parts = line.strip().split("\t")
            if len(parts) < 19:
                continue
            batch.append(parts[:19])
            if len(batch) >= 10000:
                cur.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
                con.commit(); batch.clear()
                print(f"{i} Zeilen importiert...")
        if batch:
            cur.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            con.commit()
    con.close()
    print("✅ Fertig! Datenbank gespeichert als", DB_PATH)

if __name__ == "__main__":
    import_file()
