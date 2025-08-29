<# fox_quickcheck.ps1 — Umgebung & Status für CrownFox
   Ausführen (im Projektordner):
     cd C:\Users\Aben.Michiele\Projekte\foxtest
     .\fox_quickcheck.ps1
#>

param(
  [string]$BaseUrl = "http://127.0.0.1:8010"
)

$ErrorActionPreference = "Continue"

function Title($n,$t){ Write-Host "`n==== [$n] $t ====" -ForegroundColor Cyan }

Title 0 "Projekt & PowerShell"
Write-Host ("PWD: " + (Get-Location))
Write-Host ("User: " + $env:USERNAME)
Write-Host ("PS Version: " + $PSVersionTable.PSVersion)

Title 1 ".venv aktivieren (falls vorhanden)"
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
  try { & .\.venv\Scripts\Activate.ps1; Write-Host "venv aktiviert." -ForegroundColor Green } catch { Write-Warning "Konnte .venv nicht aktivieren." }
} else {
  Write-Host ".venv nicht gefunden (ist ok, wenn globales Python genutzt wird)." -ForegroundColor Yellow
}
# --- Kein Ternary (PS5): sauber lösen
$venvVal = "<none>"
if ($env:VIRTUAL_ENV) { $venvVal = $env:VIRTUAL_ENV }
Write-Host ("VIRTUAL_ENV: " + $venvVal)

Title 2 "Python & Pakete"
try { python --version } catch { Write-Warning "python nicht im PATH?" }
try { py -V } catch {}
Write-Host "`nInstallierte Kern-Pakete:"
$names = "sounddevice","vosk","pyttsx3","scikit-learn","numpy","joblib","fastapi","uvicorn"
foreach($n in $names){
  try{
    $info = pip show $n 2>$null
    if($LASTEXITCODE -eq 0){
      ($info | Select-String "Name|Version") -join " | " | Write-Host
    } else {
      Write-Host "$($n): not installed" -ForegroundColor Yellow
    }
  } catch {
    Write-Host "$($n): not installed" -ForegroundColor Yellow
  }
}

Title 3 "Fox-Paket importierbar?"
try{
  python -c "import fox; import fox.speech_in, fox.speech_out, fox.labels; print('fox import ok')"
}catch{
  Write-Warning "fox konnte nicht importiert werden (Paketstruktur/Startordner prüfen)."
}

Title 4 "Geo-DB vorhanden?"
$geoDb = Join-Path (Get-Location) "geo_data\geo.db"
Write-Host ("geo_data\geo.db exists: " + (Test-Path $geoDb))

Title 5 "Wetter-Key gesetzt?"
if ($env:OPENWEATHER_KEY) {
  $prefix = $env:OPENWEATHER_KEY.Substring(0, [Math]::Min(4,$env:OPENWEATHER_KEY.Length))
  Write-Host ("OPENWEATHER_KEY: " + $prefix + "****")
} else {
  Write-Host "OPENWEATHER_KEY: <not set>" -ForegroundColor Yellow
}

Title 6 "Server erreichbar?"
try{
  $t = Test-NetConnection -ComputerName 127.0.0.1 -Port 8010 -WarningAction SilentlyContinue
  Write-Host ("Port 8010 open: " + $t.TcpTestSucceeded)
}catch{}
try{
  $root = Invoke-RestMethod -Uri ($BaseUrl + "/") -TimeoutSec 3
  Write-Host ("GET / ok. Name: " + $root.name + ", Version: " + $root.version)
}catch{
  Write-Host "GET / fehlgeschlagen (Server läuft evtl. nicht?)" -ForegroundColor Yellow
}

Title 7 "Mikrofone (Input-Devices)"
try{
  python -c "from fox.speech_in import SpeechIn; SpeechIn.list_input_devices()"
}catch{
  Write-Host "Konnte Mikro-Liste nicht abrufen (sounddevice/vosk?)" -ForegroundColor Yellow
}

Title 8 "Kurzer Handle-Test (optional)"
try{
  $resp = Invoke-RestMethod -Uri ($BaseUrl + "/handle") -Method POST -ContentType "application/json" -Body (@{text="wie spät ist es?"}|ConvertTo-Json) -TimeoutSec 5
  Write-Host ("Handle-Reply: " + $resp.reply)
}catch{
  Write-Host "Handle-Test übersprungen/fehlgeschlagen (Server nicht aktiv?)" -ForegroundColor Yellow
}

Title 9 "Fertig"
Write-Host "Kopiere ALLES oben und sende es hier im Chat." -ForegroundColor Green
