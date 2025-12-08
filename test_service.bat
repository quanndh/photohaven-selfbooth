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
set "TEMP_PY=test_imports.py"
(
echo import sys
echo import os
echo sys.path.insert(0, os.path.normpath(r"!SCRIPT_DIR!"))
echo import watchdog
echo import yaml
echo import PIL
echo import numpy
echo import colorama
echo print('OK')
) > "%TEMP_PY%"
python "%TEMP_PY%" 2>&1
if !ERRORLEVEL! NEQ 0 (
    del "%TEMP_PY%" 2>nul
    echo ERROR: Missing required packages!
    echo Please run: pip install -r requirements.txt
    exit /b 1
)
del "%TEMP_PY%" 2>nul

set "TEMP_PY=test_rawpy.py"
(
echo import sys
echo import os
echo sys.path.insert(0, os.path.normpath(r"!SCRIPT_DIR!"))
echo try:
echo     import rawpy
echo     print('OK (rawpy available)')
echo except ImportError:
echo     exit(1)
) > "%TEMP_PY%"
python "%TEMP_PY%" 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo WARNING: rawpy not available (RAW processing will be disabled)
    echo If you need RAW support, install rawpy or use Python 3.9-3.13
)
del "%TEMP_PY%" 2>nul
echo.

echo [5/6] Testing config file...
set "TEMP_PY=test_config.py"
(
echo import sys
echo import os
echo sys.path.insert(0, os.path.normpath(r"!SCRIPT_DIR!"))
echo import yaml
echo from pathlib import Path
echo config = yaml.safe_load(open('config.yaml'))
echo print('Config OK')
echo print('  Watch folder:', config.get('watch_folder', 'NOT SET'))
echo print('  Preset path:', config.get('preset_path', 'NOT SET'))
) > "%TEMP_PY%"
python "%TEMP_PY%" 2>&1
if !ERRORLEVEL! NEQ 0 (
    del "%TEMP_PY%" 2>nul
    echo ERROR: Config file is invalid!
    exit /b 1
)
del "%TEMP_PY%" 2>nul
echo.

echo [6/6] Testing main module import...
set "TEMP_PY=test_main.py"
(
echo import sys
echo import os
echo sys.path.insert(0, os.path.normpath(r"!SCRIPT_DIR!"))
echo import main
echo print('OK')
) > "%TEMP_PY%"
python "%TEMP_PY%" 2>&1
if !ERRORLEVEL! NEQ 0 (
    del "%TEMP_PY%" 2>nul
    echo ERROR: Cannot import main module!
    echo Check the error above for details.
    exit /b 1
)
del "%TEMP_PY%" 2>nul
echo.

echo ========================================
echo All checks passed!
echo You can now install the service.
echo ========================================
echo.
pause

