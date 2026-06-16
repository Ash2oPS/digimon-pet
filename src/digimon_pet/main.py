from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from digimon_pet.app.main_window import PetWindow
from digimon_pet.app.tray import create_app_icon, create_tray_icon


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Digimon desktop pet.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--normal", action="store_true", help="Run as a framed Qt debug window, not as a desktop pet.")
    mode.add_argument("--overlay", action="store_true", help="Run as a transparent desktop pet overlay.")
    parser.add_argument("--debug", action="store_true", help="Speed up time. Stats panel stays hidden until right-click toggle.")
    parser.add_argument("--smoke-ms", type=int, default=0, help="Auto-close after this many ms.")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setWindowIcon(create_app_icon())
    app.setQuitOnLastWindowClosed(False)
    window = PetWindow(overlay=not args.normal or args.overlay, debug=args.debug)
    tray = create_tray_icon(app, window)
    window.show()

    if args.smoke_ms > 0:
        QTimer.singleShot(args.smoke_ms, app.quit)

    exit_code = app.exec()
    tray.hide()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
