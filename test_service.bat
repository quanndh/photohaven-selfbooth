@echo off
REM Diagnostic script to test if the service can run
REM Run this before installing the service to identify issues

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "!SCRIPT_DIR!"

echo ========================================
echo Service Diagnostic Test
echo ========================================
echo.

echo [1/6] Checking Python...
python --version
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Python not found!
    exit /b 1
)
echo OK
echo.

echo [2/6] Checking Python path...
where python
echo.

echo [3/6] Checking required files...
if not exist "main.py" (
    echo ERROR: main.py not found!
    exit /b 1
)
if not exist "config.yaml" (
    echo ERROR: config.yaml not found!
    exit /b 1
)
echo OK
echo.

echo [4/6] Testing Python imports...
python -c "import sys; sys.path.insert(0, '!SCRIPT_DIR!'); import watchdog; import yaml; import PIL; import numpy; import colorama; print('OK');" 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Missing required packages!
    echo Please run: pip install -r requirements.txt
    exit /b 1
)

python -c "import sys; sys.path.insert(0, '!SCRIPT_DIR!'); import rawpy; print('OK (rawpy available)');" 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo WARNING: rawpy not available (RAW processing will be disabled)
    echo If you need RAW support, install rawpy or use Python 3.9-3.13
)
echo.

echo [5/6] Testing config file...
python -c "import sys; sys.path.insert(0, '!SCRIPT_DIR!'); import yaml; from pathlib import Path; config = yaml.safe_load(open('config.yaml')); print('Config OK'); print('  Watch folder:', config.get('watch_folder', 'NOT SET')); print('  Preset path:', config.get('preset_path', 'NOT SET'));" 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Config file is invalid!
    exit /b 1
)
echo.

echo [6/6] Testing main module import...
python -c "import sys; sys.path.insert(0, '!SCRIPT_DIR!'); import main; print('OK');" 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Cannot import main module!
    echo Check the error above for details.
    exit /b 1
)
echo.

echo ========================================
echo All checks passed!
echo You can now install the service.
echo ========================================
echo.
pause

