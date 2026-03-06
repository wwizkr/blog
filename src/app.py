from __future__ import annotations

import os
import sys

# QWebEngine(Chromium) DirectComposition 경고 억제
_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
_extra = "--disable-gpu --disable-gpu-compositing --disable-direct-composition --use-angle=swiftshader"
if _extra not in _flags:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{_flags} {_extra}".strip()
os.environ.setdefault("QT_OPENGL", "software")

from PySide6.QtWidgets import QApplication

from storage.database import init_database
from collector.scheduler import collect_scheduler
from labeling.scheduler import labeling_auto_scheduler
from writer.scheduler import writer_auto_scheduler
from ui.main_window import MainWindow


def run() -> None:
    app = QApplication(sys.argv)
    init_database()
    collect_scheduler.start()
    labeling_auto_scheduler.start()
    writer_auto_scheduler.start()
    app.aboutToQuit.connect(collect_scheduler.stop)
    app.aboutToQuit.connect(labeling_auto_scheduler.stop)
    app.aboutToQuit.connect(writer_auto_scheduler.stop)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())



