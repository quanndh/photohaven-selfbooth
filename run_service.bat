@echo off
REM Windows Service Wrapper Script
REM This script ensures proper error handling and logging for the Windows service

setlocal

REM Get the script directory
set "SCRIPT_DIR=%~dp0"
cd /d "!SCRIPT_DIR!"

REM Redirect all output to log files
call python main.py >> service_output.log 2>> service_error.log

REM If Python exits with an error, log it
if !ERRORLEVEL! NEQ 0 (
    echo Service exited with error code !ERRORLEVEL! >> service_error.log
    exit /b !ERRORLEVEL!
)

endlocal

