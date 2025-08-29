<# =====================================================================
  test_fox_api.ps1  –  End-to-end Tests für deinen CrownFox-Server
  Ausführen im Projektordner:
    cd C:\Users\Aben.Michiele\Projekte\foxtest
    .\.venv\Scripts\Activate.ps1   # optional
    .\test_fox_api.ps1
  Optional-Parameter:
    .\test_fox_api.ps1 -BaseUrl "http://127.0.0.1:8010" -OpenWeatherKey "XYZ"
===================================================================== #>

param(
  [string]$BaseUrl = "http://127.0.0.1:8010"
)

$ErrorActionPreference = "Stop"

function Write-Title([int]$n, [string]$title) {
  Write-Host ""
  Write-Host ("="*70) -ForegroundColor DarkGray
  Write-Host ("{0:00} — {1}" -f $n, $title) -ForegroundColor Cyan
  Write-Host ("="*70) -ForegroundColor DarkGray
}

function Get-Json([string]$path) {
  return Invoke-RestMethod -Uri ($BaseUrl + $path) -Method GET
}

function Post-Json([string]$path, $bodyObj) {
  $json = $bodyObj | ConvertTo-Json -Depth 8
  return Invoke-RestMethod -Uri ($BaseUrl + $path) -Method POST -Body $json -ContentType "application/json"
}

# --- 0) venv (best effort) + Wetter-Key setzen ---
Write-Title 0 "vorbereitung"
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
  try { & .\.venv\Scripts\Activate.ps1 } catch { Write-Warning "Konnte .venv nicht aktivieren (ist ok, wenn schon aktiv)." }
} else {
  Write-Host "Hinweis: .venv\Scripts\Activate.ps1 nicht gefunden – fahre fort..." -ForegroundColor Yellow
}

# --- 1) Status ---
Write-Title 1 "status – /"
$stat = Get-Json "/"
$stat | ConvertTo-Json -Depth 8 | Write-Output

# --- 2) Antwort generieren (Handle) ---
Write-Title 2 "handle – 'Wetter in Bern'"
$resp1 = Post-Json "/handle" @{ text = "Wetter in Bern" }
$resp1 | ConvertTo-Json -Depth 8 | Write-Output

# --- 3) Lernen (Training + Autosave + Snapshot) ---
Write-Title 3 "learn – 'infos über zürich' => geo"
$learn = Post-Json "/learn" @{ question = "infos über zürich"; label = "geo" }
$learn | ConvertTo-Json -Depth 8 | Write-Output

# Optional: direkt danach prüfen, ob das Gelernte greift
Write-Title 3 "handle – 'infos über zürich' (nach learn)"
$resp2 = Post-Json "/handle" @{ text = "infos über zürich" }
$resp2 | ConvertTo-Json -Depth 8 | Write-Output

# --- 4) Knowledge (SQLite) ---
Write-Title 4 "knowledge – set/get/search"
$kset = Post-Json "/knowledge/set" @{ key = "firma"; value = "Crown Fox" }
$kset | ConvertTo-Json -Depth 8 | Write-Output

$kget = Get-Json "/knowledge/get?key=firma"
$kget | ConvertTo-Json -Depth 8 | Write-Output

$ksearch = Get-Json "/knowledge/search?q=fox"
$ksearch | ConvertTo-Json -Depth 8 | Write-Output

# --- 5) Speichern + Snapshot ---
Write-Title 5 "save – modell + trainingsdaten + snapshot"
$save = Post-Json "/save" @{}
$save | ConvertTo-Json -Depth 8 | Write-Output

Write-Host ""
Write-Host "Fertig. ✔  (Backups liegen unter .\backups\)" -ForegroundColor Green
# Ende