@echo off
REM WorkClock launcher — runs the app windowless via pythonw

cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" (
  echo venv missing. Run setup first.
  pause
  exit /b 1
)

start "" "venv\Scripts\pythonw.exe" "main.py"
