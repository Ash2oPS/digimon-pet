#!/bin/sh
set -u

cd "$(dirname "$0")" || exit 1
VENV_PY=".venv/bin/python"
DIGIMON_PET_SILENT="${DIGIMON_PET_SILENT:-0}"
PYTHON_EXE=""

pause_on_error() {
    if [ "$DIGIMON_PET_SILENT" = "1" ]; then
        return
    fi
    echo
    printf "Press Enter to close this window..."
    read _answer
}

find_python() {
    for candidate in python3.12 python3.11 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
            printf "%s" "$candidate"
            return 0
        fi
    done
    return 1
}

if [ ! -x "$VENV_PY" ]; then
    if ! PYTHON_EXE="$(find_python)"; then
        echo "python3 was not found. Install Python 3.11 or newer, then run this file again."
        pause_on_error
        exit 1
    fi

    if ! "$PYTHON_EXE" -m venv .venv; then
        echo "Failed to create the Python virtual environment."
        pause_on_error
        exit 1
    fi
fi

if ! "$VENV_PY" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
    echo "The existing .venv uses Python older than 3.11. Delete .venv, then run this file again."
    pause_on_error
    exit 1
fi

if ! "$VENV_PY" -c "import PySide6, cryptography" >/dev/null 2>&1; then
    if ! "$VENV_PY" -m pip install -e .; then
        echo "Failed to install Digimon Pet dependencies."
        pause_on_error
        exit 1
    fi
fi

exec "$VENV_PY" -m digimon_pet --overlay "$@"
