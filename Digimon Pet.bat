@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "VENV_PY=.venv\Scripts\python.exe"
set "UPDATE_CHECK=packaging\windows\launcher_update_check.ps1"
set "PYTHON_EXE="

if exist "%UPDATE_CHECK%" if not "%DIGIMON_PET_UPDATE_CHECKED%"=="1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UPDATE_CHECK%"
    set "UPDATE_EXIT_CODE=%ERRORLEVEL%"
    if "%UPDATE_EXIT_CODE%"=="10" (
        call "%~f0" %*
        exit /b %ERRORLEVEL%
    )
)

if not exist "%VENV_PY%" (
    call :find_python
    if not defined PYTHON_EXE (
        echo Python 3.11+ was not found. Trying to install Python 3.12 with winget...
        call :install_python
        call :find_python
    )

    if not defined PYTHON_EXE (
        echo Python 3.11+ is required but could not be found or installed.
        echo Install Python from https://www.python.org/downloads/windows/ and enable "Add python.exe to PATH".
        if not "%DIGIMON_PET_SILENT%"=="1" pause
        exit /b 1
    )

    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 (
        echo Failed to create the Python virtual environment.
        if not "%DIGIMON_PET_SILENT%"=="1" pause
        exit /b 1
    )
)

"%VENV_PY%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    "%VENV_PY%" -m pip install --upgrade pip
    if errorlevel 1 (
        echo Failed to update pip.
        if not "%DIGIMON_PET_SILENT%"=="1" pause
        exit /b 1
    )

    "%VENV_PY%" -m pip install -e .
    if errorlevel 1 (
        echo Failed to install Digimon Pet dependencies.
        if not "%DIGIMON_PET_SILENT%"=="1" pause
        exit /b 1
    )
)

"%VENV_PY%" -m digimon_pet --overlay %*
if errorlevel 1 (
    echo Digimon Pet exited with an error.
    if not "%DIGIMON_PET_SILENT%"=="1" pause
    exit /b 1
)

exit /b 0

:find_python
set "PYTHON_EXE="
call :try_python py -3.12
if defined PYTHON_EXE exit /b 0
call :try_python py -3.11
if defined PYTHON_EXE exit /b 0
call :try_python py -3
if defined PYTHON_EXE exit /b 0
call :try_python python
if defined PYTHON_EXE exit /b 0
call :try_python python3
if defined PYTHON_EXE exit /b 0
call :try_python "%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PYTHON_EXE exit /b 0
call :try_python "%LocalAppData%\Programs\Python\Python311\python.exe"
if defined PYTHON_EXE exit /b 0
call :try_python "%ProgramFiles%\Python312\python.exe"
if defined PYTHON_EXE exit /b 0
call :try_python "%ProgramFiles%\Python311\python.exe"
if defined PYTHON_EXE exit /b 0
call :try_python "%ProgramFiles(x86)%\Python312\python.exe"
if defined PYTHON_EXE exit /b 0
call :try_python "%ProgramFiles(x86)%\Python311\python.exe"
exit /b 1

:try_python
set "_PY_CMD=%~1"
set "_PY_ARG=%~2"
if not exist "%_PY_CMD%" (
    if "%_PY_CMD%"=="%_PY_CMD:\=%" (
        where "%_PY_CMD%" >nul 2>nul || exit /b 1
    ) else (
        exit /b 1
    )
)

if "%_PY_ARG%"=="" (
    for /f "usebackq delims=" %%P in (`"%_PY_CMD%" -c "import sys; sys.exit(1) if sys.version_info < (3, 11) else print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
) else (
    for /f "usebackq delims=" %%P in (`"%_PY_CMD%" "%_PY_ARG%" -c "import sys; sys.exit(1) if sys.version_info < (3, 11) else print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
)
if defined PYTHON_EXE exit /b 0
exit /b 1

:install_python
where winget >nul 2>nul
if errorlevel 1 exit /b 1

winget install --id Python.Python.3.12 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    winget install --id Python.Python.3.12 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements --force
)
if errorlevel 1 (
    winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements --force
)
exit /b %ERRORLEVEL%
