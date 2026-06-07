"""시스템 트레이 + 글로벌 단축키(Ctrl+Shift+E).

pynput 리스너는 별도 스레드에서 돌기 때문에, 콜백에서 Qt 위젯을 직접 건드리면 안 된다.
→ QObject 시그널(스레드 안전, 큐 연결)로 메인 스레드에 토글을 전달한다.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap

from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import icons
from .widget import ExcelHelperWidget

try:
    from pynput import keyboard as _pynput_keyboard
except Exception:  # pragma: no cover - pynput 미설치/플랫폼 이슈
    _pynput_keyboard = None


def make_icon() -> QIcon:
    """엑셀 느낌의 초록 라운드 배경 + Google grid(table) 아이콘."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#2e7d32"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 12, 12)
    grid = icons.pixmap("table_chart", "white", 36)
    p.drawPixmap(14, 14, grid)
    p.end()
    return QIcon(pm)


class HotkeyBridge(QObject):
    """pynput(다른 스레드) → Qt 메인 스레드로 토글 신호 전달."""

    toggle = pyqtSignal()


class TrayController:
    def __init__(self, app: QApplication, widget: ExcelHelperWidget):
        self.app = app
        self.widget = widget
        # 자기 참조를 위젯에 심어 GC 방지. 호출측이 반환값을 저장하지 않아도
        # (예: `TrayController(app, w)`) 위젯이 살아있는 한 함께 살아남는다.
        widget._tray_controller = self
        self.icon = make_icon()
        widget.setWindowIcon(self.icon)

        self.tray = QSystemTrayIcon(self.icon, parent=widget)
        self.tray.setToolTip("엑셀 헬프 위젯 (Ctrl+Shift+E)")
        # 메뉴는 위젯을 부모로 (부모 없는 QMenu 는 Windows 트레이에서 클릭이
        # 안 먹는 경우가 있음) + 참조 유지
        self.menu = self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

        self.bridge = HotkeyBridge()
        self.bridge.toggle.connect(widget.toggle_visibility, Qt.ConnectionType.QueuedConnection)
        self._hotkey = None
        self._start_hotkey()

    # ----------------------------------------------------------------- 메뉴
    def _build_menu(self) -> QMenu:
        menu = QMenu(self.widget)  # 부모 위젯 지정
        show_act = QAction("표시 / 숨김  (Ctrl+Shift+E)", menu)
        show_act.triggered.connect(self.widget.toggle_visibility)
        menu.addAction(show_act)

        side_act = QAction("왼쪽 ↔ 오른쪽 전환", menu)
        side_act.setToolTip("사이드바를 반대쪽 가장자리로 옮깁니다")
        side_act.triggered.connect(self._toggle_side_and_show)
        menu.addAction(side_act)

        reload_act = QAction("데이터 다시 읽기", menu)
        reload_act.setToolTip("excel_functions.json 을 다시 읽어 반영(자동 감시 백업)")
        reload_act.triggered.connect(self.widget.reload_data_now)
        menu.addAction(reload_act)

        menu.addSeparator()
        quit_act = QAction("종료", menu)
        quit_act.triggered.connect(self.quit)
        menu.addAction(quit_act)
        return menu

    def _toggle_side_and_show(self) -> None:
        self.widget.show_and_focus()
        self.widget.toggle_side()

    def _on_activated(self, reason) -> None:
        # 트레이 아이콘 더블클릭/클릭 → 토글
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.widget.toggle_visibility()

    # ----------------------------------------------------------------- 글로벌 핫키
    def _start_hotkey(self) -> None:
        if _pynput_keyboard is None:
            return
        try:
            self._hotkey = _pynput_keyboard.GlobalHotKeys(
                {"<ctrl>+<shift>+e": self.bridge.toggle.emit}
            )
            self._hotkey.daemon = True
            self._hotkey.start()
        except Exception:
            self._hotkey = None  # 핫키 실패해도 트레이로는 동작

    # ----------------------------------------------------------------- 종료
    def quit(self) -> None:
        # 각 단계가 실패해도 종료는 반드시 진행되도록 모두 가드
        try:
            self.widget._persist_geometry()
            self.widget.settings.save()
        except Exception:
            pass
        try:
            self.widget.hide()
        except Exception:
            pass
        if self._hotkey is not None:
            try:
                self._hotkey.stop()
            except Exception:
                pass
        try:
            self.widget.shutdown()  # watchdog Observer 정리
        except Exception:
            pass
        try:
            self.tray.hide()
        except Exception:
            pass
        self.app.quit()
