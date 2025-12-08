@echo off
REM Windows Service Installation Script
REM Installs the Lightroom Preset Auto-Processor as a Windows Service using NSSM

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SERVICE_NAME=LightroomPresetProcessor"
set "PYTHON_PATH="

echo ========================================
echo Lightroom Preset Auto-Processor
echo Windows Service Installation
echo ========================================
echo.

REM Find Python - avoid Microsoft Store shim
echo Searching for Python installation...

REM Check common Python installation locations first (most recent first)
for %%v in (313 312 311 310 39) do (
    if exist "C:\Python%%v\python.exe" (
        set "PYTHON_PATH=C:\Python%%v\python.exe"
        goto :python_found
    )
    if exist "C:\Program Files\Python%%v\python.exe" (
        set "PYTHON_PATH=C:\Program Files\Python%%v\python.exe"
        goto :python_found
    )
)

REM Check user AppData (Python.org installer)
if exist "%LOCALAPPDATA%\Programs\Python" (
    for /f "delims=" %%i in ('dir /b /s "%LOCALAPPDATA%\Programs\Python\Python*\python.exe" 2^>nul ^| sort /r') do (
        set "PYTHON_PATH=%%i"
        goto :python_found
    )
)

REM Check PATH but skip WindowsApps shim
for /f "delims=" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 (
        "%%i" --version >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_PATH=%%i"
            goto :python_found
        )
    )
)

:python_found
if "!PYTHON_PATH!"=="" (
    echo ERROR: Python not found
    pause
    exit /b 1
)

echo Python found: !PYTHON_PATH!
"!PYTHON_PATH!" --version
echo.

REM Check for NSSM
where nssm >nul 2>&1
if !errorlevel! neq 0 (
    echo ERROR: NSSM not found in PATH
    pause
    exit /b 1
)
echo NSSM found.
echo.

REM Check for config.yaml
if not exist "!SCRIPT_DIR!config.yaml" (
    echo ERROR: config.yaml missing in script directory
    pause
    exit /b 1
)
echo Config file found.
echo.

REM Remove old service
echo Removing existing service if present...
nssm stop !SERVICE_NAME! >nul 2>&1
nssm remove !SERVICE_NAME! confirm >nul 2>&1
timeout /t 1 >nul

echo Installing service...

REM Install service with Python executable only
nssm install !SERVICE_NAME! "!PYTHON_PATH!"

REM Set correct working directory
nssm set !SERVICE_NAME! AppDirectory "!SCRIPT_DIR!"

REM Correct script argument (NO ESCAPING PROBLEMS)
nssm set !SERVICE_NAME! AppParameters "\"!SCRIPT_DIR!main.py\""

REM Display info
nssm set !SERVICE_NAME! DisplayName "Lightroom Preset Auto-Processor"
nssm set !SERVICE_NAME! Description "Applies Lightroom presets to images automatically"

REM Logs
nssm set !SERVICE_NAME! AppStdout "!SCRIPT_DIR!service_output.log"
nssm set !SERVICE_NAME! AppStderr "!SCRIPT_DIR!service_error.log"

REM Use LocalSystem
nssm set !SERVICE_NAME! ObjectName LocalSystem

REM Auto start
nssm set !SERVICE_NAME! Start SERVICE_AUTO_START

REM Use current PATH inside service
set "CURRENT_PATH=%PATH%"
nssm set !SERVICE_NAME! AppEnvironmentExtra "PATH=%CURRENT_PATH%"

echo Service installed successfully!
echo.

echo Starting service...
nssm start !SERVICE_NAME!
timeout /t 2 >nul

nssm status !SERVICE_NAME! >nul 2>&1
if !errorlevel! neq 0 (
    echo WARNING: Service did not start properly.
    echo Check logs:
    echo    type "!SCRIPT_DIR!service_error.log"
) else (
    echo Service started successfully!
    echo Logs at:
    echo   service_output.log
    echo   service_error.log
)

echo.
echo ========================================
echo Service Management Commands:
echo ========================================
echo sc query !SERVICE_NAME!
echo nssm start !SERVICE_NAME!
echo nssm stop !SERVICE_NAME!
echo nssm restart !SERVICE_NAME!
echo nssm remove !SERVICE_NAME! confirm
echo ========================================
pause