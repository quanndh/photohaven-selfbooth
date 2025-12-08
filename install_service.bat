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

REM Find Python
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "delims=" %%i in ('where python') do set "PYTHON_PATH=%%i"
)

if "!PYTHON_PATH!"=="" (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.9 or later and add it to PATH
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

REM Remove existing service if it exists
echo Removing existing service if present...
nssm stop !SERVICE_NAME! >nul 2>&1
nssm remove !SERVICE_NAME! confirm >nul 2>&1
timeout /t 1 >nul

REM Install service
echo Installing service...
nssm install !SERVICE_NAME! "!PYTHON_PATH!" "!SCRIPT_DIR!main.py"
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Failed to install service
    pause
    exit /b 1
)

nssm set !SERVICE_NAME! AppDirectory "!SCRIPT_DIR!"
nssm set !SERVICE_NAME! DisplayName "Lightroom Preset Auto-Processor"
nssm set !SERVICE_NAME! Description "Applies Lightroom presets to images automatically"
nssm set !SERVICE_NAME! Start SERVICE_AUTO_START
nssm set !SERVICE_NAME! AppStdout "!SCRIPT_DIR!service_output.log"
nssm set !SERVICE_NAME! AppStderr "!SCRIPT_DIR!service_error.log"
nssm set !SERVICE_NAME! AppExitAction Restart
nssm set !SERVICE_NAME! AppRestartDelay 5000

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
