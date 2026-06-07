"""진입점 — 데이터 로드, 위젯/트레이 부트스트랩."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, QLockFile
from PyQt6.QtWidgets import QApplication, QMessageBox

from app import paths
from app.reloader import Reloader
from app.search import DataError, load_items
from app.settings import Settings
from app.tray import TrayController
from app.widget import ExcelHelperWidget


def main() -> int:
    # HiDPI(125%/150% 등 분수 배율)에서 좌표/스케일 어긋남 방지.
    # QApplication 생성 전에 호출해야 적용됨.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Excel Helper Widget")
    # 마지막 창을 닫아도(트레이로 숨겨도) 앱이 종료되지 않게
    app.setQuitOnLastWindowClosed(False)

    # 중복 실행 방지(좀비 트레이 누적 차단). 30초 이상 stale 이면 자동 회수.
    lock = QLockFile(str(Path(tempfile.gettempdir()) / "excel_helper_widget.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(100):
        QMessageBox.information(
            None, "엑셀 헬프 위젯",
            "이미 실행 중입니다. 시스템 트레이의 아이콘(또는 Ctrl+Shift+E)을 사용하세요.",
        )
        return 0

    try:
        items = load_items(paths.data_file())
    except DataError as exc:
        QMessageBox.critical(None, "데이터 오류", str(exc))
        return 1

    settings = Settings().load()
    widget = ExcelHelperWidget(items, settings)
    # 반드시 참조를 유지해야 한다. 저장하지 않으면 TrayController 파이썬 객체가
    # 곧바로 GC 되어, 트레이 아이콘(위젯 자식이라 C++ 객체는 생존)은 보이지만
    # '종료'·'우측 도킹' 등 TrayController 메서드에 연결된 메뉴 액션 슬롯이 죽는다.
    tray = TrayController(app, widget)
    widget._tray = tray  # 위젯 수명과 함께 확실히 유지

    # JSON 핫리로드: 데이터 파일 변경 감시 → 메인 스레드로 시그널 → 디바운스 후 리로드.
    # 시작 실패(플랫폼/권한)해도 트레이의 "데이터 다시 읽기"로 수동 폴백 가능.
    reloader = Reloader(paths.data_file())
    reloader.bridge.changed.connect(
        widget.schedule_reload, Qt.ConnectionType.QueuedConnection
    )
    widget._reloader = reloader  # 참조 유지 + 종료 시 정리
    reloader.start()

    widget.show_and_focus()
    try:
        return app.exec()
    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
