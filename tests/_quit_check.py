"""실제 exec() 루프에서 '종료' 액션이 프로세스를 정말 끝내는지(행 안 걸리는지) 측정."""
import sys, time
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from app import paths
from app.search import load_items
from app.settings import Settings, DEFAULTS
from app.widget import ExcelHelperWidget
from app.tray import TrayController

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
st = Settings(path=paths._external_dir()/"tests"/"_quit_tmp.json"); st._data = dict(DEFAULTS)
w = ExcelHelperWidget(load_items(paths.data_file()), st)
tray = TrayController(app, w)
w.show()

t0 = time.time()
def fire_quit():
    print("[t=%.2f] '종료' 액션 트리거" % (time.time()-t0))
    tray.tray.contextMenu().actions()[-1].trigger()

# 워치독: 종료가 안 되면 강제로 알림 후 탈출
def watchdog():
    print("[t=%.2f] !!! 아직 살아있음 — 종료가 행 걸림 !!!" % (time.time()-t0))
    QApplication.quit()

QTimer.singleShot(600, fire_quit)
QTimer.singleShot(3000, watchdog)
rc = app.exec()
print("[t=%.2f] exec() 반환 rc=%d (프로세스 곧 종료)" % (time.time()-t0, rc))
