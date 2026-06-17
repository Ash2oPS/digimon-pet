@echo off
setlocal

cd /d "%~dp0"
set "VENV_PY=.venv\Scripts\python.exe"
set "UPDATE_CHECK=packaging\windows\launcher_update_check.ps1"

if exist "%UPDATE_CHECK%" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UPDATE_CHECK%"
)

if not exist "%VENV_PY%" (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )

    if %ERRORLEVEL% NEQ 0 (
        echo Failed to create the Python virtual environment.
        if not "%DIGIMON_PET_SILENT%"=="1" pause
        exit /b %ERRORLEVEL%
    )
)

"%VENV_PY%" -c "import PySide6" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    "%VENV_PY%" -m pip install -e .
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install Digimon Pet dependencies.
        if not "%DIGIMON_PET_SILENT%"=="1" pause
        exit /b %ERRORLEVEL%
    )
)

"%VENV_PY%" -m digimon_pet --overlay %*
if %ERRORLEVEL% NEQ 0 (
    echo Digimon Pet exited with an error.
    if not "%DIGIMON_PET_SILENT%"=="1" pause
    exit /b %ERRORLEVEL%
)
