@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  echo Build dependency installation failed.
  pause
  exit /b 1
)
py -3 -m PyInstaller --clean --onefile --windowed --name LINEStampCutter --collect-all PIL line_stamp_cutter.py
if errorlevel 1 (
  echo Build failed. See the PyInstaller output above.
  pause
  exit /b 1
)
echo Built: dist\LINEStampCutter.exe
pause
