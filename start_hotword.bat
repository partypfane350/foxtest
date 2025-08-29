@echo off
cd /d "%~dp0"
call .\.venv\Scripts\activate.bat
set FOX_LANG=de
REM Optional: spezifisches Mikro wählen, z. B. Index 1
REM set FOX_MIC=1
python hotword.py