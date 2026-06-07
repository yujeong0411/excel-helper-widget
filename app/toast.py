"""복사 토스트 — 짧게 나타났다 사라지는 알림(스펙 §4.4)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QWidget


class Toast(QLabel):
    """부모 위젯 하단 중앙에 잠깐 떠오르는 메시지."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "#toast { background: rgba(40,40,40,0.92); color: white;"
            " border-radius: 8px; padding: 6px 14px; font-size: 12px; }"
        )
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, msec: int = 1500) -> None:
        self.setText(text)
        self.adjustSize()
        p = self.parentWidget()
        if p is not None:
            x = (p.width() - self.width()) // 2
            y = p.height() - self.height() - 24
            self.move(max(0, x), max(0, y))
        self.show()
        self.raise_()
        self._timer.start(msec)
