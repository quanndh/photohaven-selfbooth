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
(
echo import sys
echo sys.path.insert(0, r"!SCRIPT_DIR!")
echo import watchdog
echo import yaml
echo import PIL
echo import numpy
echo import colorama
echo print('OK')
) > test_imports.py
python test_imports.py 2>&1
if !ERRORLEVEL! NEQ 0 (
    del test_imports.py 2>nul
    echo ERROR: Missing required packages!
    echo Please run: pip install -r requirements.txt
    exit /b 1
)
del test_imports.py 2>nul

(
echo import sys
echo sys.path.insert(0, r"!SCRIPT_DIR!")
echo try:
echo     import rawpy
echo     print('OK (rawpy available)')
echo except ImportError:
echo     exit(1)
) > test_rawpy.py
python test_rawpy.py 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo WARNING: rawpy not available (RAW processing will be disabled)
    echo If you need RAW support, install rawpy or use Python 3.9-3.13
)
del test_rawpy.py 2>nul
echo.

echo [5/6] Testing config file...
(
echo import sys
echo sys.path.insert(0, r"!SCRIPT_DIR!")
echo import yaml
echo from pathlib import Path
echo config = yaml.safe_load(open('config.yaml'))
echo print('Config OK')
echo print('  Watch folder:', config.get('watch_folder', 'NOT SET'))
echo print('  Preset path:', config.get('preset_path', 'NOT SET'))
) > test_config.py
python test_config.py 2>&1
if !ERRORLEVEL! NEQ 0 (
    del test_config.py 2>nul
    echo ERROR: Config file is invalid!
    exit /b 1
)
del test_config.py 2>nul
echo.

echo [6/6] Testing main module import...
(
echo import sys
echo sys.path.insert(0, r"!SCRIPT_DIR!")
echo import main
echo print('OK')
) > test_main.py
python test_main.py 2>&1
if !ERRORLEVEL! NEQ 0 (
    del test_main.py 2>nul
    echo ERROR: Cannot import main module!
    echo Check the error above for details.
    exit /b 1
)
del test_main.py 2>nul
echo.

echo ========================================
echo All checks passed!
echo You can now install the service.
echo ========================================
echo.
pause

