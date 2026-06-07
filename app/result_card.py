"""결과 카드 위젯 — 접힘/펼침 + 예시 복사 + 즐겨찾기 + related 링크."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .search import Item

_CODE_FONT = "Consolas, 'D2Coding', 'Courier New', monospace"
_STAR_ON = "#f5a623"
_STAR_OFF = "#c4c4c4"


class ResultCard(QFrame):
    """기능 하나를 표현하는 카드.

    - 접힘: 별 토글 + 이름(굵게) + 한 줄 목적
    - 펼침: 구문 / 예시(+복사) / 주의 / 단축키 / 관련 링크
    """

    toggled = pyqtSignal()
    copyRequested = pyqtSignal(str)        # 복사할 텍스트
    activated = pyqtSignal(object)         # 이 카드가 선택됨 (self 전달)
    favoriteToggled = pyqtSignal(str, bool)  # (id, 새 상태)
    relatedClicked = pyqtSignal(str)       # 클릭한 related 항목 id

    def __init__(
        self,
        item: Item,
        parent: QWidget | None = None,
        *,
        is_favorite: bool = False,
        name_of: dict[str, str] | None = None,
    ):
        super().__init__(parent)
        self.item = item
        self._expanded = False
        self._selected = False
        self._is_fav = is_favorite
        self._name_of = name_of or {}
        self.setObjectName("card")
        self._build()
        self._apply_style()

    # ----------------------------------------------------------------- UI 구성
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)

        # 헤더: 별 토글 + 이름 + 카테고리
        self.star_btn = QPushButton()
        self.star_btn.setObjectName("starBtn")
        self.star_btn.setFixedSize(24, 24)
        self.star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.star_btn.setToolTip("즐겨찾기")
        self.star_btn.clicked.connect(self._on_star)
        self._refresh_star()

        self._name = QLabel(self.item.name)
        self._name.setObjectName("cardName")
        self._name.setTextFormat(Qt.TextFormat.PlainText)
        self._purpose = QLabel(self.item.purpose)
        self._purpose.setObjectName("cardPurpose")
        self._purpose.setWordWrap(True)

        cat = QLabel(self.item.category)
        cat.setObjectName("cardCat")

        header_top = QHBoxLayout()
        header_top.setSpacing(6)
        header_top.addWidget(self.star_btn, 0, Qt.AlignmentFlag.AlignTop)
        header_top.addWidget(self._name)
        header_top.addStretch(1)
        header_top.addWidget(cat, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header_top)
        outer.addWidget(self._purpose)

        # 상세(펼침) 영역
        self._detail = QWidget()
        dl = QVBoxLayout(self._detail)
        dl.setContentsMargins(0, 6, 0, 0)
        dl.setSpacing(6)

        dl.addWidget(self._kv("구문", self.item.syntax, code=True))

        if self.item.example:
            row = QHBoxLayout()
            ex = self._kv("예시", self.item.example, code=True)
            ex.setProperty("isExample", True)
            row.addWidget(ex, 1)
            btn = QPushButton()
            btn.setObjectName("copyBtn")
            btn.setIcon(icons.icon("content_copy", "#2e7d32", 16))
            btn.setToolTip("예시 복사")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(34)
            btn.clicked.connect(self._on_copy)
            row.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)
            dl.addLayout(row)

        if self.item.shortcut:
            dl.addWidget(self._kv("단축키", self.item.shortcut))
        if self.item.note:
            dl.addWidget(self._kv("주의", self.item.note))

        # 관련(related) 링크 — 데이터에 존재하는 id만
        rel = [(rid, self._name_of[rid]) for rid in self.item.related if rid in self._name_of]
        if rel:
            rel_row = QHBoxLayout()
            rel_row.setSpacing(6)
            rel_row.addWidget(self._tag_label("관련"))
            for rid, rname in rel:
                link = QPushButton(rname)
                link.setObjectName("relatedChip")
                link.setCursor(Qt.CursorShape.PointingHandCursor)
                link.clicked.connect(lambda _=False, i=rid: self.relatedClicked.emit(i))
                rel_row.addWidget(link)
            rel_row.addStretch(1)
            dl.addLayout(rel_row)

        self._detail.setVisible(False)
        outer.addWidget(self._detail)

    def _tag_label(self, text: str) -> QLabel:
        w = QLabel(f"<b>{text}</b>")
        w.setTextFormat(Qt.TextFormat.RichText)
        return w

    def _kv(self, label: str, value: str, code: bool = False) -> QLabel:
        w = QLabel(f"<b>{label}</b>  {value}" if not code
                   else f"<b>{label}</b>  <span style=\"font-family:{_CODE_FONT}\">{_esc(value)}</span>")
        w.setTextFormat(Qt.TextFormat.RichText)
        w.setWordWrap(True)
        w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return w

    # ----------------------------------------------------------------- 즐겨찾기
    def _refresh_star(self) -> None:
        name = "star_fill1" if self._is_fav else "star"
        color = _STAR_ON if self._is_fav else _STAR_OFF
        self.star_btn.setIcon(icons.icon(name, color, 18))

    def _on_star(self) -> None:
        self._is_fav = not self._is_fav
        self._refresh_star()
        self.favoriteToggled.emit(self.item.id, self._is_fav)

    def is_favorite(self) -> bool:
        return self._is_fav

    # ----------------------------------------------------------------- 동작
    def mousePressEvent(self, event):  # noqa: N802 (Qt 시그니처)
        self.activated.emit(self)
        self.toggle()
        super().mousePressEvent(event)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, value: bool) -> None:
        self._expanded = value
        self._detail.setVisible(value)
        self.toggled.emit()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_selected(self, value: bool) -> None:
        self._selected = value
        self._apply_style()

    def copy_example(self) -> bool:
        """예시가 있으면 복사 요청. 복사 가능 여부 반환."""
        if self.item.example:
            self._on_copy()
            return True
        return False

    def _on_copy(self) -> None:
        if self.item.example:
            self.copyRequested.emit(self.item.example)

    # ----------------------------------------------------------------- 스타일
    def _apply_style(self) -> None:
        border = "#2e7d32" if self._selected else "#d9d9d9"
        bg = "#f1f8f1" if self._selected else "#ffffff"
        self.setStyleSheet(
            f"#card {{ background:{bg}; border:1px solid {border}; border-radius:8px; }}"
            "#cardName { font-weight:bold; font-size:14px; color:#1f1f1f; }"
            "#cardPurpose { color:#555; font-size:12px; }"
            "#cardCat { color:#888; font-size:10px; }"
            "#starBtn { border:none; background:transparent; }"
            "#starBtn:hover { background:rgba(245,166,35,0.15); border-radius:4px; }"
            "#copyBtn { border:1px solid #cfcfcf; border-radius:6px;"
            " background:#fafafa; padding:2px; }"
            "#copyBtn:hover { background:#e8f5e9; }"
            "#relatedChip { border:1px solid #cfe3cf; border-radius:10px;"
            " background:#f1f8f1; color:#2e7d32; font-size:11px; padding:2px 9px; }"
            "#relatedChip:hover { background:#e0f0e0; border:1px solid #2e7d32; }"
        )


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
