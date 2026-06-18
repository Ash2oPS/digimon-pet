@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "VENV_PY=.venv\Scripts\python.exe"
set "LOCAL_PY=.local\python312\python.exe"
set "LOCAL_PY_DIR=.local\python312"
set "PYTHON_INSTALLER=.local\python-3.12.10-amd64.exe"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "UPDATE_CHECK=packaging\windows\launcher_update_check.ps1"
set "PYTHON_EXE="

if exist "%UPDATE_CHECK%" if not "%DIGIMON_PET_UPDATE_CHECKED%"=="1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UPDATE_CHECK%"
    set "UPDATE_EXIT_CODE=%ERRORLEVEL%"
    if "!UPDATE_EXIT_CODE!"=="10" (
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
        echo Python still was not found. Forcing Python 3.12 repair with winget...
        call :install_python_force
        call :find_python
    )

    if not defined PYTHON_EXE (
        echo Python still was not found. Installing a local Python runtime...
        call :install_python_local
        call :find_python
    )

    if not defined PYTHON_EXE (
        echo Python 3.11+ is required but could not be found or installed.
        echo Install Python from https://www.python.org/downloads/windows/ and enable "Add python.exe to PATH".
        if not "%DIGIMON_PET_SILENT%"=="1" pause
        exit /b 1
    )

    "!PYTHON_EXE!" -m venv .venv
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
if exist "%LOCAL_PY%" (
    for %%P in ("%LOCAL_PY%") do set "PYTHON_EXE=%%~fP"
    exit /b 0
)
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
set "_PY_PROBE=%TEMP%\digimon_pet_python_probe_%RANDOM%.py"
if not exist "%_PY_CMD%" (
    if "%_PY_CMD%"=="%_PY_CMD:\=%" (
        where "%_PY_CMD%" >nul 2>nul || exit /b 1
    ) else (
        exit /b 1
    )
)

> "%_PY_PROBE%" echo import sys
>> "%_PY_PROBE%" echo if sys.version_info[0] != 3: sys.exit^(1^)
>> "%_PY_PROBE%" echo if sys.version_info[1] not in [11, 12, 13, 14, 15]: sys.exit^(1^)
>> "%_PY_PROBE%" echo print^(sys.executable^)

if "%_PY_ARG%"=="" (
    for /f "usebackq delims=" %%P in (`"%_PY_CMD%" "%_PY_PROBE%" 2^>nul`) do set "PYTHON_EXE=%%P"
) else (
    for /f "usebackq delims=" %%P in (`"%_PY_CMD%" "%_PY_ARG%" "%_PY_PROBE%" 2^>nul`) do set "PYTHON_EXE=%%P"
)
del "%_PY_PROBE%" >nul 2>nul
if defined PYTHON_EXE exit /b 0
exit /b 1

:install_python
where winget >nul 2>nul
if errorlevel 1 exit /b 1

winget install --id Python.Python.3.12 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements
)
exit /b %ERRORLEVEL%

:install_python_force
where winget >nul 2>nul
if errorlevel 1 exit /b 1

winget install --id Python.Python.3.12 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements --force
if errorlevel 1 (
winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements --force
)
exit /b %ERRORLEVEL%

:install_python_local
if exist "%LOCAL_PY%" exit /b 0
if not exist ".local" mkdir ".local"
if errorlevel 1 exit /b 1

if not exist "%PYTHON_INSTALLER%" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%PYTHON_INSTALLER%'"
    if errorlevel 1 exit /b 1
)

start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 TargetDir="%CD%\%LOCAL_PY_DIR%" Include_launcher=0 PrependPath=0 Include_pip=1 Include_tcltk=1 Include_test=0 Shortcuts=0
if errorlevel 1 exit /b 1
if not exist "%LOCAL_PY%" exit /b 1
exit /b 0
