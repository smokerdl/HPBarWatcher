"""Application entry point for HPBarWatcher."""
from __future__ import annotations

import ctypes
import sys


def _enable_windows_dpi_awareness() -> None:
    """Make Qt and MSS use the same physical-pixel coordinate space on Windows."""
    if sys.platform != "win32":
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def main() -> int:
    _enable_windows_dpi_awareness()

    from PySide6.QtWidgets import QApplication
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("HPBarWatcher")
    app.setOrganizationName("HPBarWatcher")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
