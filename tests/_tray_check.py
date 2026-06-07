"""실제 플랫폼: 트레이 메뉴 popup 가시성 + 단일 인스턴스 잠금 확인."""
import sys, tempfile
from pathlib import Path
from PyQt6.QtCore import QPoint, QTimer, QLockFile
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from app import paths
from app.search import load_items
from app.settings import Settings, DEFAULTS
from app.widget import ExcelHelperWidget
from app.tray import TrayController

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

# 1) 단일 인스턴스 잠금
lockpath = str(Path(tempfile.gettempdir()) / "excel_helper_widget.lock")
l1 = QLockFile(lockpath); l1.setStaleLockTime(30_000)
print("첫 잠금 획득:", l1.tryLock(100))
l2 = QLockFile(lockpath); l2.setStaleLockTime(30_000)
print("두번째 잠금 거부(=False여야 정상):", l2.tryLock(100))

st = Settings(path=paths._external_dir()/"tests"/"_tray_tmp.json"); st._data = dict(DEFAULTS)
w = ExcelHelperWidget(load_items(paths.data_file()), st)
tray = TrayController(app, w)
w.show()

# 2) 메뉴 popup 가시성
menu = tray.tray.contextMenu()
print("menu parent is widget:", menu.parent() is w)

def check():
    menu.popup(QPoint(400, 400))
    app.processEvents()
    print("메뉴 popup 표시됨(visible):", menu.isVisible())
    print("액션:", [a.text() for a in menu.actions() if a.text()])
    menu.close()
    app.quit()

QTimer.singleShot(300, check)
app.exec()
l1.unlock()
print("done")
