from PyQt6.QtWidgets import QWidget, QApplication
old_show = QWidget.show

def debug_show(self):
    title = self.windowTitle()
    cls = type(self).__name__
    print(f"SHOW: {cls} | title={title!r}")
    return old_show(self)

QWidget.show = debug_show

import main
from PyQt6.QtCore import QTimer

def stop():
    print("Stopping via timer...")
    app = QApplication.instance()
    if app:
        app.quit()

QTimer.singleShot(3000, stop)
main.main()
