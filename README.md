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

um db zu installieren
cd  .\geo_data
python geo_import.py 
 
src ornder erstellen
New-Item -ItemType Directory -Force -Path .\geo_data\src, .\geo_data\src\postal | Out-Null

GeoNames-Dateien herunterlade
# Basis-URL
$base = "https://download.geonames.org/export/dump/"

# Pflicht
Invoke-WebRequest -Uri ($base + "countryInfo.txt")       -OutFile .\geo_data\src\countryInfo.txt
Invoke-WebRequest -Uri ($base + "admin1CodesASCII.txt")  -OutFile .\geo_data\src\admin1CodesASCII.txt
Invoke-WebRequest -Uri ($base + "admin2Codes.txt")       -OutFile .\geo_data\src\admin2Codes.txt
Invoke-WebRequest -Uri ($base + "allCountries.zip")      -OutFile .\geo_data\src\allCountries.zip
Invoke-WebRequest -Uri ($base + "alternateNamesV2.zip")  -OutFile .\geo_data\src\alternateNamesV2.zip

# OPTIONAL: Postleitzahlen
Invoke-WebRequest -Uri "https://download.geonames.org/export/zip/allCountries.zip" `
  -OutFile .\geo_data\src\postal\allCountries.zip