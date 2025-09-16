## Installing Python Virtual Environments (`venv`)

1. **Ensure Python is installed**  
    Check if Python is installed by running:
    ```sh
    python --version
    ```
    If not installed, download it from [python.org](https://www.python.org/downloads/).

2. **Create a virtual environment**  
    Run the following command in your project directory:
    ```sh
    python -m venv venv
    ```
    This creates a folder named `venv` containing the virtual environment.

3. **Activate the virtual environment**

    - **Windows:**
      ```sh
      .\venv\Scripts\activate
      ```
    - **macOS/Linux:**
      ```sh
      source venv/bin/activate
      ```

4. **Deactivate when done**  
    To exit the virtual environment, run:
    ```sh
    deactivate
    ```

 http://127.0.0.1:8010/chat

# um db zu installieren
cd  .\geo_data
python geo_import.py 
 
# src ornder erstellen
New-Item -ItemType Directory -Force -Path .\geo_data\src, .\geo_data\src\postal | Out-Null


# Sicherstellen, dass geo_data\src existiert
if (-not (Test-Path .\geo_data\src)) { New-Item -Path .\geo_data\src -ItemType Directory -Force | Out-Null }

# GeoNames-Dateien herunterladen
Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/countryInfo.txt"       -OutFile .\geo_data\src\countryInfo.txt
Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/admin1CodesASCII.txt"  -OutFile .\geo_data\src\admin1CodesASCII.txt
Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/admin2Codes.txt"       -OutFile .\geo_data\src\admin2Codes.txt
Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/allCountries.zip"      -OutFile .\geo_data\src\allCountries.zip
Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/alternateNamesV2.zip"  -OutFile .\geo_data\src\alternateNamesV2.zip
Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/timeZones.txt"         -OutFile .\geo_data\src\timeZones.txt

# Sicherstellen, dass geo_data\osm existiert
if (-not (Test-Path .\geo_data\osm)) {
    New-Item -Path .\geo_data\osm -ItemType Directory -Force | Out-Null
}

# Europa-OSM von Geofabrik herunterladen
Invoke-WebRequest -Uri "https://download.geofabrik.de/europe-latest.osm.pbf"  -OutFile .\geo_data\osm\europe-latest.osm.pbf
Invoke-WebRequest -Uri "https://download.geofabrik.de/africa-latest.osm.pbf"       -OutFile .\geo_data\osm\africa-latest.osm.pbf
Invoke-WebRequest -Uri "https://download.geofabrik.de/asia-latest.osm.pbf"         -OutFile .\geo_data\osm\asia-latest.osm.pbf
Invoke-WebRequest -Uri "https://download.geofabrik.de/north-america-latest.osm.pbf" -OutFile .\geo_data\osm\north-america-latest.osm.pbf
Invoke-WebRequest -Uri "https://download.geofabrik.de/south-america-latest.osm.pbf" -OutFile .\geo_data\osm\south-america-latest.osm.pbf
Invoke-WebRequest -Uri "https://download.geofabrik.de/oceania-latest.osm.pbf"      -OutFile .\geo_data\osm\oceania-latest.osm.pbf
Invoke-WebRequest -Uri "https://download.geofabrik.de/antarctica-latest.osm.pbf"   -OutFile .\geo_data\osm\antarctica-latest.osm.pbf
