@echo off
setlocal
title REVIVE — Autonomous Revenue Recovery Decision System

echo ================================================================================
echo       REVIVE — AUTONOMOUS REVENUE RECOVERY DECISION SYSTEM
echo ================================================================================
echo.

REM Check if Python virtual environment exists
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [*] Validating local runtime environment and dependencies...
%PYTHON_EXE% -c "from core.environment_validator import EnvironmentValidator; is_val, errs, _ = EnvironmentValidator.validate(); print('[+] Environment Valid: ' + str(is_val)); exit(0 if is_val else 1)"
if errorlevel 1 (
    echo [!] Environment validation failed. Please check dependencies.
    pause
    exit /b 1
)

echo.
echo [*] Starting REVIVE Interactive Control Center Web Server...
echo [*] Web Application URL : http://127.0.0.1:8000
echo [*] API Documentation   : http://127.0.0.1:8000/docs
echo.
%PYTHON_EXE% -m server.cli --port 8000 --host 127.0.0.1

endlocal
