@echo off
REM Install and run using PM2 (Process Manager 2)
REM PM2 works great with Python scripts and is much simpler than NSSM

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "APP_NAME=lightroom-preset-processor"

echo ========================================
echo Lightroom Preset Auto-Processor
echo PM2 Installation (Recommended)
echo ========================================
echo.

REM Check for Node.js (required for PM2)
where node >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Node.js not found
    echo.
    echo PM2 requires Node.js. Please install from:
    echo https://nodejs.org/
    echo.
    echo After installing Node.js, run this script again.
    pause
    exit /b 1
)

echo Node.js found.
node --version
echo.

REM Check for PM2
where pm2 >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo PM2 not found. Installing PM2 globally...
    npm install -g pm2
    if !ERRORLEVEL! NEQ 0 (
        echo ERROR: Failed to install PM2
        pause
        exit /b 1
    )
)

echo PM2 found.
pm2 --version
echo.

REM Find Python - avoid Microsoft Store shim
set "PYTHON_PATH="

REM Check common Python installation locations
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

REM Check user AppData
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

REM Check for config.yaml
if not exist "!SCRIPT_DIR!config.yaml" (
    echo ERROR: config.yaml missing
    pause
    exit /b 1
)

echo Config file found.
echo.

REM Stop existing PM2 process if running
pm2 stop !APP_NAME! >nul 2>&1
pm2 delete !APP_NAME! >nul 2>&1

REM Start with PM2
echo Starting application with PM2...
cd /d "!SCRIPT_DIR!"
pm2 start "!PYTHON_PATH!" --name "!APP_NAME!" -- "main.py"
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: Failed to start with PM2
    pause
    exit /b 1
)

REM Save PM2 process list (so it persists after reboot)
pm2 save

REM Setup PM2 to start on Windows boot
pm2 startup | findstr /i "pm2-startup" >nul
if !ERRORLEVEL! EQU 0 (
    echo.
    echo IMPORTANT: Run the command shown above as Administrator to enable auto-start on boot
    echo.
) else (
    REM Try to generate startup script
    pm2 startup > "%TEMP%\pm2_startup.txt" 2>&1
    type "%TEMP%\pm2_startup.txt"
    del "%TEMP%\pm2_startup.txt" 2>nul
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Application is running with PM2.
echo.
echo Useful PM2 commands:
echo   pm2 list              - Show all processes
echo   pm2 logs !APP_NAME!   - View logs
echo   pm2 restart !APP_NAME! - Restart
echo   pm2 stop !APP_NAME!   - Stop
echo   pm2 delete !APP_NAME! - Remove
echo   pm2 monit             - Monitor dashboard
echo.
pause

