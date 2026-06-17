#!/bin/sh
set -u

cd "$(dirname "$0")" || exit 1
VENV_PY=".venv/bin/python"

pause_on_error() {
    echo
    printf "Press Enter to close this window..."
    read _answer
}

if [ ! -x "$VENV_PY" ]; then
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv .venv
    else
        echo "python3 was not found. Install Python 3.11 or newer, then run this file again."
        pause_on_error
        exit 1
    fi

    if [ $? -ne 0 ]; then
        echo "Failed to create the Python virtual environment."
        pause_on_error
        exit 1
    fi
fi

if ! "$VENV_PY" -c "import PySide6" >/dev/null 2>&1; then
    if ! "$VENV_PY" -m pip install -e .; then
        echo "Failed to install Digimon Pet dependencies."
        pause_on_error
        exit 1
    fi
fi

exec "$VENV_PY" -m digimon_pet --overlay "$@"
