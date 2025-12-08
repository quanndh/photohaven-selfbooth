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
set "PYTHON_PATH="

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

REM Check user AppData (common for Python.org installers)
if exist "%LOCALAPPDATA%\Programs\Python" (
    for /f "delims=" %%i in ('dir /b /s "%LOCALAPPDATA%\Programs\Python\Python*\python.exe" 2^>nul ^| sort /r') do (
        set "PYTHON_PATH=%%i"
        goto :python_found
    )
)

REM Check PATH but skip Microsoft Store shim
for /f "delims=" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if !ERRORLEVEL! NEQ 0 (
        REM Verify it's a real Python executable
        "%%i" --version >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            set "PYTHON_PATH=%%i"
            goto :python_found
        )
    )
)

:python_found
if "!PYTHON_PATH!"=="" (
    echo ERROR: Python not found
    echo.
    echo Please install Python 3.9 or later from python.org:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

REM Verify it's not the Microsoft Store shim
echo !PYTHON_PATH! | findstr /i "WindowsApps" >nul
if !ERRORLEVEL! EQU 0 (
    echo ERROR: Found Microsoft Store Python shim, not a real installation
    echo.
    echo Please install Python from python.org instead:
    echo https://www.python.org/downloads/
    echo.
    echo Or manually set PYTHON_PATH at the top of this script.
    echo.
    pause
    exit /b 1
)

echo Python found: !PYTHON_PATH!
python --version
echo.

REM Check if NSSM is available
where nssm >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: NSSM is required to install as a Windows Service.
    echo.
    echo Please download NSSM from: https://nssm.cc/download
    echo Extract it and add the 64-bit or 32-bit folder to your PATH.
    echo.
    echo Alternatively, you can use Task Scheduler to run at startup.
    echo See WINDOWS_INSTALL.md for detailed instructions.
    echo.
    pause
    exit /b 1
)

echo NSSM found.
echo.

REM Check if config.yaml exists
if not exist "!SCRIPT_DIR!config.yaml" (
    echo ERROR: config.yaml not found in !SCRIPT_DIR!
    echo Please create config.yaml before installing the service.
    pause
    exit /b 1
)

echo Config file found.
echo.

REM Skip test - if manual run works, proceed with installation

REM Remove existing service if it exists
echo Removing existing service if present...
nssm stop !SERVICE_NAME! >nul 2>&1
nssm remove !SERVICE_NAME! confirm >nul 2>&1
timeout /t 1 >nul

REM Install service
echo Installing service...
nssm install !SERVICE_NAME! "!PYTHON_PATH!"
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Failed to install service
    pause
    exit /b 1
)

nssm set !SERVICE_NAME! AppDirectory "!SCRIPT_DIR!"
nssm set !SERVICE_NAME! AppParameters "\"!SCRIPT_DIR!main.py\""
nssm set !SERVICE_NAME! DisplayName "Lightroom Preset Auto-Processor"
nssm set !SERVICE_NAME! Description "Applies Lightroom presets to images automatically"
nssm set !SERVICE_NAME! Start SERVICE_AUTO_START
nssm set !SERVICE_NAME! AppStdout "!SCRIPT_DIR!service_output.log"
nssm set !SERVICE_NAME! AppStderr "!SCRIPT_DIR!service_error.log"

REM Get current PATH and set it for the service
echo %PATH% > "%TEMP%\service_path.txt"
for /f "usebackq delims=" %%a in ("%TEMP%\service_path.txt") do set "CURRENT_PATH=%%a"
del "%TEMP%\service_path.txt" 2>nul
nssm set !SERVICE_NAME! AppEnvironmentExtra "PATH=!CURRENT_PATH!"

echo Service installed successfully!
echo.

REM Start service
echo Starting service...
timeout /t 2 >nul
nssm start !SERVICE_NAME!
timeout /t 2 >nul

REM Check status
nssm status !SERVICE_NAME! >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo Service started successfully!
    echo.
    echo Service is running. Check logs if you encounter any issues:
    echo   - service_output.log
    echo   - service_error.log
    echo   - preset_processor.log
) else (
    echo WARNING: Service may not have started properly.
    echo.
    echo Please check the error logs:
    echo   type "!SCRIPT_DIR!service_error.log"
    echo.
    echo Common issues:
    echo   1. Missing dependencies: pip install -r requirements.txt
    echo   2. Invalid config.yaml: Check watch_folder and preset_path
    echo   3. Try running manually: python main.py
)

echo.
echo ========================================
echo Service Management Commands:
echo ========================================
echo Check status:  sc query !SERVICE_NAME!
echo Start:         nssm start !SERVICE_NAME!
echo Stop:          nssm stop !SERVICE_NAME!
echo Restart:       nssm restart !SERVICE_NAME!
echo Remove:        nssm stop !SERVICE_NAME! ^&^& nssm remove !SERVICE_NAME! confirm
echo.
pause
