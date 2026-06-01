@echo off
setlocal enabledelayedexpansion

:: Aconsegueix el directori del script (equival a SCRIPT_DIR)
set "SCRIPT_DIR=%~dp0"

:: Calcula el PROJECT_ROOT anant 3 nivells cap enrere
type cd "%SCRIPT_DIR%..\..\.." >nul 2>&1
pushd "%SCRIPT_DIR%..\..\.."
set "PROJECT_ROOT=%CD%"
popd

:: Ruta al Python del venv a Windows
set "VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"

:: Comprova si el venv existeix
if not exist "%VENV_PYTHON%" (
    echo Error: venv not found at %PROJECT_ROOT%\venv
    echo Please create a virtual environment first.
    exit /b 1
)

:: Comprova si fastapi està instal·lat
"%VENV_PYTHON%" -c "import fastapi" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing GUI dependencies...
    "%VENV_PYTHON%" -m pip install fastapi uvicorn
)

echo Starting VeraGrid GUI at http://localhost:8550
"%VENV_PYTHON%" "%SCRIPT_DIR%dashboard.py"

pause