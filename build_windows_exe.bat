@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found. Please install Python 3 first.
  pause
  exit /b 1
)

echo Installing/updating PyInstaller...
py -3 -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo Failed to install PyInstaller.
  pause
  exit /b 1
)

echo Checking Qt dependency...
py -3 -c "import importlib.util,sys;sys.exit(0 if (importlib.util.find_spec('PyQt6') or importlib.util.find_spec('PyQt5')) else 1)"
if errorlevel 1 (
  echo PyQt not found, installing PyQt6...
  py -3 -m pip install --upgrade PyQt6
  if errorlevel 1 (
    echo Failed to install PyQt6.
    pause
    exit /b 1
  )
)

echo.
echo Building JustDraw.exe ...
py -3 build_exe.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Build succeeded: dist\JustDraw.exe
pause
