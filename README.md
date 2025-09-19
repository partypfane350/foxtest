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

5. **Server**
    die seite ist hier [Fox](http://127.0.0.1:8010/chat).

6. **um db zu installieren:**
    ```sh
    cd  .\geo_data
    python geo_import.py 
    ```
 
7. **src ornder erstellen:**
    ```sh
    New-Item -ItemType Directory -Force -Path .\geo_data\src, .\geo_data\src\postal | Out-Null
    ```

8. **Sicherstellen, dass geo_data\src existiert:**
        ```sh
        if (-not (Test-Path .\geo_data\src)) { New-Item -Path .\geo_data\src -ItemType Directory -Force | Out-Null }
        ```

9. **GeoNames-Dateien herunterladen:**
        ```sh
        Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/countryInfo.txt"       -OutFile .\geo_data\src\countryInfo.txt
        Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/admin1CodesASCII.txt"  -OutFile .\geo_data\src\admin1CodesASCII.txt
        Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/admin2Codes.txt"       -OutFile .\geo_data\src\admin2Codes.txt
        Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/allCountries.zip"      -OutFile .\geo_data\src\allCountries.zip
        Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/alternateNamesV2.zip"  -OutFile .\geo_data\src\alternateNamesV2.zip
        Invoke-WebRequest -Uri "https://download.geonames.org/export/dump/timeZones.txt"         -OutFile .\geo_data\src\timeZones.txt
        ```

10. **Sicherstellen, dass geo_data\osm existiert:**
        ```sh
        if (-not (Test-Path .\geo_data\osm)) {New-Item -Path .\geo_data\osm -ItemType Directory -Force | Out-Null}
        ```

11. **Welt-OSM von Geofabrik herunterladen:**    
        ```sh
        Invoke-WebRequest -Uri "https://download.geofabrik.de/europe-latest.osm.pbf"  -OutFile .\geo_data\osm\europe-latest.osm.pbf
        Invoke-WebRequest -Uri "https://download.geofabrik.de/africa-latest.osm.pbf"       -OutFile .\geo_data\osm\africa-latest.osm.pbf
        Invoke-WebRequest -Uri "https://download.geofabrik.de/asia-latest.osm.pbf"         -OutFile .\geo_data\osm\asia-latest.osm.pbf
        Invoke-WebRequest -Uri "https://download.geofabrik.de/north-america-latest.osm.pbf" -OutFile .\geo_data\osm\north-america-latest.osm.pbf
        Invoke-WebRequest -Uri "https://download.geofabrik.de/south-america-latest.osm.pbf" -OutFile .\geo_data\osm\south-america-latest.osm.pbf
        Invoke-WebRequest -Uri "https://download.geofabrik.de/oceania-latest.osm.pbf"      -OutFile .\geo_data\osm\oceania-latest.osm.pbf
        Invoke-WebRequest -Uri "https://download.geofabrik.de/antarctica-latest.osm.pbf"   -OutFile .\geo_data\osm\antarctica-latest.osm.pbf
        ```
12. **Bio DB**

# Allgemeines Wissen (Wikipedia / Wikidata)
if (-not (Test-Path .\bio_dumps\wikipedia)) {New-Item -Path .\bio_dumps\wikipedia -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2" -Destination "C:\bio_dumps\enwiki-latest-pages-articles.xml.bz2"

if (-not (Test-Path .\bio_dumps\wikidata)) {New-Item -Path .\bio_dumps\wikidata -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://dumps.wikimedia.org/wikidatawiki/latest/wikidatawiki-latest-all.json.bz2" -Destination "C:\bio_dumps\wikidata-latest-all.json.bz2"

# Arten- und Biodiversitätsdaten
if (-not (Test-Path .\bio_dumps\catalogue_of_life)) {New-Item -Path .\bio_dumps\catalogue_of_life -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://download.catalogueoflife.org/col/monthly/col.zip" -Destination "C:\bio_dumps\col.zip"

if (-not (Test-Path .\bio_dumps\gbif)) {New-Item -Path .\bio_dumps\gbif -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://hosted-datasets.gbif.org/datasets/occurrence/occurrence_part01.zip" -Destination "C:\bio_dumps\occurrence_part01.zip"
Start-BitsTransfer -Source "https://hosted-datasets.gbif.org/datasets/occurrence/occurrence_part02.zip" -Destination "C:\bio_dumps\occurrence_part02.zip"
Start-BitsTransfer -Source "https://hosted-datasets.gbif.org/datasets/occurrence/occurrence_part03.zip" -Destination "C:\bio_dumps\occurrence_part03.zip"

# Genetische und molekulare Daten
if (-not (Test-Path .\bio_dumps\genbank)) {New-Item -Path .\bio_dumps\genbank -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "ftp://ftp.ncbi.nlm.nih.gov/genbank/gbrel.txt" -Destination "C:\bio_dumps\genbank_release.txt"

if (-not (Test-Path .\bio_dumps\uniprot)) {New-Item -Path .\bio_dumps\uniprot -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.dat.gz" -Destination "C:\bio_dumps\uniprot_sprot.dat.gz"
Start-BitsTransfer -Source "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_trembl.dat.gz" -Destination "C:\bio_dumps\uniprot_trembl.dat.gz"

if (-not (Test-Path .\bio_dumps\ensembl)) {New-Item -Path .\bio_dumps\ensembl -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "ftp://ftp.ensembl.org/pub/release-112/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz" -Destination "C:\bio_dumps\homo_sapiens_GRCh38.fa.gz"

# Biomedizinisches Wissen
if (-not (Test-Path .\bio_dumps\pubmed)) {New-Item -Path .\bio_dumps\pubmed -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/oa_comm_xml.incr.2025-09-01.tar.gz" -Destination "C:\bio_dumps\pubmed_oa.tar.gz"

13. **Chemie**
# hinweis
PubChem FTP: https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/
Dort siehst du alle aktuellen .sdf.gz Dateien.
Kopiere die aktuellste Datei und ersetze sie im PowerShell-Befehl.

ChEMBL FTP: https://ftp.ebi.ac.uk/pub/databases/chembl/
Wähle das neueste Release (chembl_33, chembl_34 usw.).
Link einfach in deinen Befehl einsetzen.

ZINC, PubMed, DrugBank → analog: immer die aktuellste Version vom FTP/Download-Link nehmen.

# PubChem (Substances / Compounds)
if (-not (Test-Path .\chem_data\pubchem_compounds)) {New-Item -Path .\chem_data\pubchem_compounds -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/Compound_2025_01_01.sdf.gz" -Destination ".\chem_data\pubchem_compounds\Compound_2025_01_01.sdf.gz"

# ChEMBL (Bioaktive Moleküle)
if (-not (Test-Path .\chem_data\chembl)) {New-Item -Path .\chem_data\chembl -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_33/chembl_33_sqlite.tar.gz" -Destination ".\chem_data\chembl\chembl_33_sqlite.tar.gz"

# DrugBank (Arzneistoffe) (Registrierung erforderlich, Beispiel für kostenlosen XML-Dump)
if (-not (Test-Path .\chem_data\drugbank)) {New-Item -Path .\chem_data\drugbank -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://go.drugbank.com/releases/latest/downloads/all-full-database" -Destination ".\chem_data\drugbank\drugbank_latest.xml"

# ZINC Database (Moleküle für Screening)
if (-not (Test-Path .\chem_data\zinc)) {New-Item -Path .\chem_data\zinc -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "http://files.docking.org/zinc15/ZINC15_molecules_01.sdf.gz" -Destination ".\chem_data\zinc\ZINC15_molecules_01.sdf.gz"

# NIST Chemistry WebBook (Physikochemische Daten)
if (-not (Test-Path .\chem_data\nist)) {New-Item -Path .\chem_data\nist -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://webbook.nist.gov/chemistry/thermo/NISTwebbook_data.zip" -Destination ".\chem_data\nist\NISTwebbook_data.zip"

# PubChem BioAssay (Bioaktivitätsdaten)
if (-not (Test-Path .\chem_data\pubchem_bioassay)) {New-Item -Path .\chem_data\pubchem_bioassay -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ftp.ncbi.nlm.nih.gov/pubchem/Bioassay/CSV/2025/BioAssay_2025_01_01.csv.gz" -Destination ".\chem_data\pubchem_bioassay\BioAssay_2025_01_01.csv.gz"

14. **Psychologie**

# PubMed / PubMed Central (psychologische Artikel)
if (-not (Test-Path .\psych_data\pubmed)) {New-Item -Path .\psych_data\pubmed -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/oa_comm_xml.incr.2025-09-01.tar.gz" -Destination ".\psych_data\pubmed\pubmed_oa_2025-09-01.tar.gz"

# Open-Source Psychometrics Project (Tests & Rohdaten)
if (-not (Test-Path .\psych_data\openpsychometrics)) {New-Item -Path .\psych_data\openpsychometrics -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://openpsychometrics.org/_rawdata/bigfive.csv" -Destination ".\psych_data\openpsychometrics\bigfive.csv"

# IPIP (International Personality Item Pool)
if (-not (Test-Path .\psych_data\ipip)) {New-Item -Path .\psych_data\ipip -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ipip.ori.org/new_ipip-50-item-scale_data.csv" -Destination ".\psych_data\ipip\ipip_50_item_scale.csv"

# Harvard Dataverse – Psychologie Datensätze
if (-not (Test-Path .\psych_data\harvard_dataverse)) {New-Item -Path .\psych_data\harvard_dataverse -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://dataverse.harvard.edu/api/access/datafile/456789" -Destination ".\psych_data\harvard_dataverse\bigfive_survey.csv"
Hinweis: Harvard Dataverse hat für jede Studie eigene Links → musst du ggf. anpassen.

# ICPSR (Inter-university Consortium for Political and Social Research)
if (-not (Test-Path .\psych_data\icpsr)) {New-Item -Path .\psych_data\icpsr -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://www.icpsr.umich.edu/web/ICPSR/studies/12345/dataset/12345.csv" -Destination ".\psych_data\icpsr\psych_survey_12345.csv"
Hinweis: ICPSR benötigt meist Registrierung → direkte Downloads funktionieren nur für offene Datensätze.

15. **Wissenschaft**

# arXiv (Preprints)
if (-not (Test-Path ".\science_data\arxiv")) {New-Item -Path ".\science_data\arxiv" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://arxiv.org/e-print/2301.00001" -Destination ".\science_data\arxiv\2301.00001.pdf"

# DOAJ (Open-Access Journals)
if (-not (Test-Path ".\science_data\doaj")) {New-Item -Path ".\science_data\doaj" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://doaj.org/csv" -Destination ".\science_data\doaj\doaj_metadata.csv"

# OpenAlex (wissenschaftliche Publikationen + Zitierungen)
if (-not (Test-Path ".\science_data\openalex")) {New-Item -Path ".\science_data\openalex" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://openalex.org/downloads/openalex-works.jsonl.gz" -Destination ".\science_data\openalex\openalex-works.jsonl.gz"

# Zenodo (interdisziplinäre Forschungsdaten)
if (-not (Test-Path ".\science_data\zenodo")) {New-Item -Path ".\science_data\zenodo" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://zenodo.org/record/1234567/files/sample_dataset.zip?download=1" -Destination ".\science_data\zenodo\sample_dataset.zip"

# Figshare (interdisziplinäre Datensätze)
if (-not (Test-Path ".\science_data\figshare")) {New-Item -Path ".\science_data\figshare" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ndownloader.figshare.com/files/12345678" -Destination ".\science_data\figshare\sample_dataset.zip"

# Harvard Dataverse
if (-not (Test-Path ".\science_data\harvard_dataverse")) {New-Item -Path ".\science_data\harvard_dataverse" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://dataverse.harvard.edu/api/access/datafile/456789" -Destination ".\science_data\harvard_dataverse\sample_dataset.csv"

# Open Science Framework (OSF)
if (-not (Test-Path ".\science_data\osf")) {New-Item -Path ".\science_data\osf" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://osf.io/download/abcdef/" -Destination ".\science_data\osf\sample_dataset.zip"

# Open Science Framework (OSF) – Bauingenieurwesen
if (-not (Test-Path ".\science_data\osf_building")) {New-Item -Path ".\science_data\osf_building" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://osf.io/download/ghijkl/" -Destination ".\science_data\osf_building\building_dataset.zip"

# Zenodo – Ingenieurwissenschaftliche Datensätze
if (-not (Test-Path ".\science_data\zenodo_building")) {New-Item -Path ".\science_data\zenodo_building" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://zenodo.org/record/2345678/files/bridge_simulation_data.zip?download=1" -Destination ".\science_data\zenodo_building\bridge_simulation_data.zip"

# Figshare – Bauingenieurwesen
if (-not (Test-Path ".\science_data\figshare_building")) {New-Item -Path ".\science_data\figshare_building" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ndownloader.figshare.com/files/23456789" -Destination ".\science_data\figshare_building\construction_dataset.zip"

16. **Architekur**

# Open Science Framework (OSF) – Architekturprojekte
if (-not (Test-Path ".\architecture_data\osf")) {New-Item -Path ".\architecture_data\osf" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://osf.io/download/abcdef/" -Destination ".\architecture_data\osf\building_project.zip"

# Zenodo – Architektur / Bauwissenschaft
if (-not (Test-Path ".\architecture_data\zenodo")) {New-Item -Path ".\architecture_data\zenodo" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://zenodo.org/record/2345678/files/architecture_simulation.zip?download=1" -Destination ".\architecture_data\zenodo\architecture_simulation.zip"

# Figshare – Architekturprojekte
if (-not (Test-Path ".\architecture_data\figshare")) {New-Item -Path ".\architecture_data\figshare" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ndownloader.figshare.com/files/34567890" -Destination ".\architecture_data\figshare\building_data.zip"

17. **Pyhsik**

# arXiv – Physik-Preprints
if (-not (Test-Path ".\physics_data\arxiv")) {New-Item -Path ".\physics_data\arxiv" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://arxiv.org/e-print/2301.00001" -Destination ".\physics_data\arxiv\2301.00001.pdf"

# Zenodo – Physik-Datasets
if (-not (Test-Path ".\physics_data\zenodo")) {New-Item -Path ".\physics_data\zenodo" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://zenodo.org/record/3456789/files/physics_experiment.zip?download=1" -Destination ".\physics_data\zenodo\physics_experiment.zip"

# Figshare – Physikprojekte
if (-not (Test-Path ".\physics_data\figshare")) {New-Item -Path ".\physics_data\figshare" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://ndownloader.figshare.com/files/45678901" -Destination ".\physics_data\figshare\physics_dataset.zip"

# OpenAlex / DOAJ – Physikpublikationen
if (-not (Test-Path ".\physics_data\openalex")) {New-Item -Path ".\physics_data\openalex" -ItemType Directory -Force | Out-Null}
Start-BitsTransfer -Source "https://openalex.org/downloads/openalex-works.jsonl.gz" -Destination ".\physics_data\openalex\openalex-works.jsonl.gz"
