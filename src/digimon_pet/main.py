from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from digimon_pet.app.main_window import PetWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Digimon desktop pet.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--normal", action="store_true", help="Run as a normal debug window.")
    mode.add_argument("--overlay", action="store_true", help="Run as a transparent overlay.")
    parser.add_argument("--debug", action="store_true", help="Show debug controls and speed up time.")
    parser.add_argument("--smoke-ms", type=int, default=0, help="Auto-close after this many ms.")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    window = PetWindow(overlay=not args.normal, debug=args.debug)
    window.show()

    if args.smoke_ms > 0:
        QTimer.singleShot(args.smoke_ms, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

