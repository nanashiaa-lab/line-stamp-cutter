@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  echo Build dependency installation failed.
  pause
  exit /b 1
)
py -3 -c "import PIL; print('Bundled Pillow will be:', PIL.__version__)"
REM v1.0.1: dropped --collect-all PIL (it dragged in unused numpy) and exclude numpy explicitly.
py -3 -m PyInstaller --clean --onefile --windowed --name LINEStampCutter --exclude-module numpy line_stamp_cutter.py
if errorlevel 1 (
  echo Build failed. See the PyInstaller output above.
  pause
  exit /b 1
)
echo Built: dist\LINEStampCutter.exe
pause
