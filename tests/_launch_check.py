"""실제 플랫폼에서 전체 부팅(트레이+핫키 포함)이 예외 없이 뜨는지 확인하고 자동 종료.

테스트 수집 대상이 아님(_ 접두). `uv run python tests/_launch_check.py` 로 직접 실행.
"""

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app import paths
from app.search import load_items
from app.settings import Settings
from app.tray import TrayController
from app.widget import ExcelHelperWidget


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    items = load_items(paths.data_file())
    print(f"[ok] 데이터 {len(items)}개 로드")

    settings = Settings().load()
    widget = ExcelHelperWidget(items, settings)
    tray = TrayController(app, widget)
    print(f"[ok] 위젯/트레이 생성, 카드 {len(widget.cards)}개 렌더")
    print(f"[ok] 글로벌 핫키 등록: {'성공' if tray._hotkey else '미등록(트레이로 동작)'}")
    print(f"[ok] 트레이 표시 가능: {tray.tray.isSystemTrayAvailable()}")

    widget.show_and_focus()
    print(f"[ok] 위젯 표시됨 visible={widget.isVisible()} 위치={widget.geometry().getRect()}")

    # 검색 동작 한 번 확인
    widget.search_box.setText("조건 합계")
    widget._run_search()
    top = widget.cards[0].item.name if widget.cards else "(없음)"
    print(f"[ok] '조건 합계' 검색 → {len(widget.cards)}개, 1위: {top}")

    QTimer.singleShot(1200, app.quit)
    rc = app.exec()
    print(f"[ok] 이벤트 루프 정상 종료 rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
