@echo off
REM Windows Service Installation Script
REM Installs the Lightroom Preset Auto-Processor as a Windows Service using NSSM

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SERVICE_NAME=LightroomPresetProcessor"
set "PYTHON_PATH="

REM Find Python
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "delims=" %%i in ('where python') do set "PYTHON_PATH=%%i"
)

if "!PYTHON_PATH!"=="" (
    echo Error: Python not found in PATH
    echo Please install Python 3.9 or later and add it to PATH
    pause
    exit /b 1
)

echo Installing Lightroom Preset Auto-Processor as Windows Service...
echo Python path: !PYTHON_PATH!
echo Script directory: !SCRIPT_DIR!
echo.

REM Check if NSSM is available
where nssm >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo NSSM is required to install as a Windows Service.
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

REM Remove existing service if it exists
nssm stop !SERVICE_NAME! >nul 2>&1
nssm remove !SERVICE_NAME! confirm >nul 2>&1

REM Test if Python can run the script first
echo Testing Python script...
"!PYTHON_PATH!" -c "import sys; sys.path.insert(0, '!SCRIPT_DIR!'); import main" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo WARNING: Python script test failed. This may cause the service to fail.
    echo Please check that all dependencies are installed:
    echo   pip install -r requirements.txt
    echo.
    echo Press any key to continue anyway, or Ctrl+C to cancel...
    pause >nul
)

REM Install service
echo Installing service...
nssm install !SERVICE_NAME! "!PYTHON_PATH!" "!SCRIPT_DIR!main.py"
nssm set !SERVICE_NAME! AppDirectory "!SCRIPT_DIR!"
nssm set !SERVICE_NAME! DisplayName "Lightroom Preset Auto-Processor"
nssm set !SERVICE_NAME! Description "Applies Lightroom presets to images automatically"
nssm set !SERVICE_NAME! Start SERVICE_AUTO_START
nssm set !SERVICE_NAME! AppStdout "!SCRIPT_DIR!service_output.log"
nssm set !SERVICE_NAME! AppStderr "!SCRIPT_DIR!service_error.log"
nssm set !SERVICE_NAME! AppExitAction Restart
nssm set !SERVICE_NAME! AppRestartDelay 5000

REM Start service
echo Starting service...
timeout /t 2 >nul
nssm start !SERVICE_NAME!

REM Wait a moment and check status
timeout /t 3 >nul
nssm status !SERVICE_NAME! >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo ERROR: Service failed to start!
    echo.
    echo Please check the error logs:
    echo   type "!SCRIPT_DIR!service_error.log"
    echo.
    echo Common issues:
    echo   1. Missing dependencies - run: pip install -r requirements.txt
    echo   2. Config file missing or invalid - check config.yaml
    echo   3. Preset file not found - check preset_path in config.yaml
    echo   4. Watch folder path invalid - check watch_folder in config.yaml
    echo.
    echo Try running manually first:
    echo   cd "!SCRIPT_DIR!"
    echo   python main.py
    echo.
) else (
    echo Service started successfully!
)

echo.
echo Service installed successfully!
echo.
echo To check service status:
echo   sc query !SERVICE_NAME!
echo.
echo To stop the service:
echo   nssm stop !SERVICE_NAME!
echo.
echo To start the service:
echo   nssm start !SERVICE_NAME!
echo.
echo To remove the service:
echo   nssm stop !SERVICE_NAME!
echo   nssm remove !SERVICE_NAME! confirm
echo.
echo Logs are available at:
echo   !SCRIPT_DIR!service_output.log
echo   !SCRIPT_DIR!service_error.log
echo   !SCRIPT_DIR!preset_processor.log
echo.

pause
