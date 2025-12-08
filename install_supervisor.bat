@echo off
REM Install and run using Supervisor (Python process manager)
REM Supervisor is a Python-native alternative to PM2

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "APP_NAME=lightroom-preset-processor"

echo ========================================
echo Lightroom Preset Auto-Processor
echo Supervisor Installation
echo ========================================
echo.

REM Find Python - avoid Microsoft Store shim
set "PYTHON_PATH="

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

if exist "%LOCALAPPDATA%\Programs\Python" (
    for /f "delims=" %%i in ('dir /b /s "%LOCALAPPDATA%\Programs\Python\Python*\python.exe" 2^>nul ^| sort /r') do (
        set "PYTHON_PATH=%%i"
        goto :python_found
    )
)

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

REM Check if supervisor is installed
"!PYTHON_PATH!" -c "import supervisor" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo Installing supervisor...
    "!PYTHON_PATH!" -m pip install supervisor
    if !ERRORLEVEL! NEQ 0 (
        echo ERROR: Failed to install supervisor
        pause
        exit /b 1
    )
)

echo Supervisor found.
echo.

REM Check for config.yaml
if not exist "!SCRIPT_DIR!config.yaml" (
    echo ERROR: config.yaml missing
    pause
    exit /b 1
)

REM Create supervisor config directory
if not exist "!SCRIPT_DIR!supervisor" mkdir "!SCRIPT_DIR!supervisor"

REM Create supervisor config file
set "SUPERVISOR_CONFIG=!SCRIPT_DIR!supervisor\supervisord.conf"
set "SUPERVISOR_LOG=!SCRIPT_DIR!supervisor\supervisord.log"
set "SUPERVISOR_PID=!SCRIPT_DIR!supervisor\supervisord.pid"

(
echo [supervisord]
echo logfile=!SUPERVISOR_LOG!
echo pidfile=!SUPERVISOR_PID!
echo.
echo [program:!APP_NAME!]
echo command=!PYTHON_PATH! main.py
echo directory=!SCRIPT_DIR!
echo autostart=true
echo autorestart=true
echo startretries=3
echo stderr_logfile=!SCRIPT_DIR!service_error.log
echo stdout_logfile=!SCRIPT_DIR!service_output.log
echo environment=PATH="%PATH%"
) > "!SUPERVISOR_CONFIG!"

echo Created supervisor config: !SUPERVISOR_CONFIG!
echo.

REM Find supervisord.exe (usually in Scripts folder)
set "SUPERVISORD="
for %%p in ("!PYTHON_PATH!") do set "PYTHON_DIR=%%~dpp"

if exist "!PYTHON_DIR!Scripts\supervisord.exe" (
    set "SUPERVISORD=!PYTHON_DIR!Scripts\supervisord.exe"
) else if exist "!PYTHON_DIR!supervisord.exe" (
    set "SUPERVISORD=!PYTHON_DIR!supervisord.exe"
) else (
    "!PYTHON_PATH!" -c "import supervisor; import os; print(os.path.join(os.path.dirname(supervisor.__file__), 'supervisord.exe'))" > "%TEMP%\supervisord_path.txt" 2>nul
    for /f "delims=" %%i in ('type "%TEMP%\supervisord_path.txt" 2^>nul') do set "SUPERVISORD=%%i"
    del "%TEMP%\supervisord_path.txt" 2>nul
)

if "!SUPERVISORD!"=="" (
    echo ERROR: Could not find supervisord.exe
    echo Please install supervisor: pip install supervisor
    pause
    exit /b 1
)

REM Stop existing supervisor if running
"!SUPERVISORD!" -c "!SUPERVISOR_CONFIG!" shutdown >nul 2>&1
timeout /t 1 >nul

REM Start supervisor
echo Starting supervisor...
cd /d "!SCRIPT_DIR!"
start "Supervisor" "!SUPERVISORD!" -c "!SUPERVISOR_CONFIG!"

timeout /t 2 >nul

REM Check if running
"!SUPERVISORD!" -c "!SUPERVISOR_CONFIG!" status >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo Supervisor started successfully!
) else (
    echo WARNING: Supervisor may not have started properly
    echo Check logs: !SUPERVISOR_LOG!
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Application is running with Supervisor.
echo.
echo Useful Supervisor commands:
echo   supervisorctl -c "!SUPERVISOR_CONFIG!" status
echo   supervisorctl -c "!SUPERVISOR_CONFIG!" restart !APP_NAME!
echo   supervisorctl -c "!SUPERVISOR_CONFIG!" stop !APP_NAME!
echo   supervisorctl -c "!SUPERVISOR_CONFIG!" start !APP_NAME!
echo.
echo To stop supervisor:
echo   "!SUPERVISORD!" -c "!SUPERVISOR_CONFIG!" shutdown
echo.
pause

