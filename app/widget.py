"""메인 위젯 — 좌/우 가장자리에 고정되는 사이드바.

핵심 동작:
- 항상 화면 왼쪽 또는 오른쪽 가장자리에 붙어 있음(가장자리에서 떨어지지 않음)
- 좌/우 전환은 시스템 트레이 메뉴에서만
- 접으면 작은 '인덱스 탭'(엑셀 느낌의 초록 탭), 클릭하면 펼침
- 타이틀바/탭 드래그로 세로 위치 이동(가로는 항상 가장자리 고정)
- 바닥 그립으로 높이, 안쪽 가장자리 그립으로 가로폭 조절
- 아이콘은 모두 Google Material Symbols
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QKeyEvent, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import icons, paths, search
from .result_card import ResultCard
from .search import ALL_CHIP, CATEGORIES, DataError, Item, load_items
from .settings import Settings
from .toast import Toast

DEFAULT_WIDTH = 360
MIN_WIDTH = 280
MAX_WIDTH = 760
COLLAPSED_WIDTH = 30          # 접힌 인덱스 탭 폭
COLLAPSED_HEIGHT = 132        # 접힌 인덱스 탭 높이
DEFAULT_HEIGHT = 600
MIN_HEIGHT = 320
GRIP_H = 7                    # 바닥 높이 그립
WGRIP_W = 6                   # 안쪽 가로폭 그립
TOP_MARGIN = 20
DEBOUNCE_MS = 120
RELOAD_DEBOUNCE_MS = 400       # 핫리로드 디바운스
RELOAD_RETRIES = 2            # 저장 도중 읽기 실패 시 재시도 횟수
FAV_LABEL = "즐겨찾기"          # 즐겨찾기 칩 라벨(카테고리 아님)
RECENT_TITLE = "최근 본 항목"
ALL_TITLE = "전체"
EXCEL_GREEN = "#2e7d32"


class FlowLayout(QLayout):
    """좁은 폭에서 자식 위젯을 자동으로 다음 줄로 흘려보내는 레이아웃(칩용)."""

    def __init__(self, parent=None, spacing: int = 4):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):  # noqa: N802
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):  # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):  # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x, y = rect.x(), rect.y()
        line_height = 0
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if x + w > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x += w + self._spacing
            line_height = max(line_height, h)
        return y + line_height - rect.y()


class SearchLineEdit(QLineEdit):
    """검색창 — 방향키/Enter/Esc/Ctrl+C 를 위젯으로 전달."""

    upPressed = pyqtSignal()
    downPressed = pyqtSignal()
    enterPressed = pyqtSignal()
    escPressed = pyqtSignal()
    copyPressed = pyqtSignal()

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        key = e.key()
        if key == Qt.Key.Key_Up:
            self.upPressed.emit(); return
        if key == Qt.Key.Key_Down:
            self.downPressed.emit(); return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enterPressed.emit(); return
        if key == Qt.Key.Key_Escape:
            self.escPressed.emit(); return
        if key == Qt.Key.Key_C and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if not self.hasSelectedText():
                self.copyPressed.emit(); return
        super().keyPressEvent(e)


class TitleBar(QFrame):
    """펼친 상태 헤더 — 접기 / 투명도 / 닫기 + 세로 드래그(가로 고정)."""

    def __init__(self, host: "ExcelHelperWidget"):
        super().__init__(host)
        self.host = host
        self.setObjectName("titlebar")
        self.setFixedHeight(34)
        self._drag_off = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 6, 0)
        lay.setSpacing(4)

        pin = QLabel()
        pin.setPixmap(icons.pixmap("push_pin", "white", 15))
        pin.setToolTip("항상 다른 창 위에 표시됩니다")
        lay.addWidget(pin)
        title = QLabel("엑셀 헬프")
        title.setObjectName("titleText")
        lay.addWidget(title)
        lay.addStretch(1)

        self.collapse_btn = QPushButton()
        self.collapse_btn.setObjectName("iconBtn")
        self.collapse_btn.setFixedSize(26, 24)
        self.collapse_btn.setToolTip("접기")
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.clicked.connect(lambda: host.set_collapsed(True))
        lay.addWidget(self.collapse_btn)

        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setFixedWidth(58)
        self.opacity.setRange(85, 100)
        self.opacity.setToolTip("투명도")
        self.opacity.valueChanged.connect(lambda v: host.set_opacity(v / 100.0))
        lay.addWidget(self.opacity)

        close = QPushButton()
        close.setObjectName("iconBtn")
        close.setIcon(icons.icon("close", "white", 16))
        close.setToolTip("트레이로 숨기기")
        close.setFixedSize(24, 24)
        close.clicked.connect(host.hide_to_tray)
        lay.addWidget(close)

    def refresh_glyphs(self, side: str) -> None:
        # 접기 방향: 오른쪽 사이드면 오른쪽(▶)으로, 왼쪽이면 왼쪽(◀)으로 접힘
        name = "chevron_right" if side == "right" else "chevron_left"
        self.collapse_btn.setIcon(icons.icon(name, "white", 18))

    # 세로 드래그(가로 고정)
    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.host.begin_v_move(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.host.do_v_move(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):  # noqa: N802
        self.host.end_v_move()


class CollapsedTab(QFrame):
    """접힌 인덱스 탭 — 엑셀 느낌의 초록 탭. 클릭하면 펼침, 드래그하면 세로 이동."""

    DRAG_THRESHOLD = 4

    def __init__(self, host: "ExcelHelperWidget"):
        super().__init__(host)
        self.host = host
        self.setObjectName("collapsedTab")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("클릭하면 펼치기 · 드래그하면 위치 이동")
        self._press_g = None
        self._moved = False
        self._side = "right"
        self._icon = icons.pixmap("table_chart", "white", 18)

    def refresh_glyphs(self, side: str) -> None:
        self._side = side
        # 화면 안쪽 면만 둥글게(탭처럼 가장자리에서 살짝 튀어나온 느낌)
        if side == "right":
            radius = ("border-top-left-radius:10px;border-bottom-left-radius:10px;"
                      "border-top-right-radius:0;border-bottom-right-radius:0;")
        else:
            radius = ("border-top-right-radius:10px;border-bottom-right-radius:10px;"
                      "border-top-left-radius:0;border-bottom-left-radius:0;")
        self.setStyleSheet(f"#collapsedTab {{ background:{EXCEL_GREEN}; {radius} }}")
        self.update()

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_g = e.globalPosition().toPoint()
            self._moved = False
            self.host.begin_v_move(self._press_g)

    def mouseMoveEvent(self, e):  # noqa: N802
        if not (e.buttons() & Qt.MouseButton.LeftButton) or self._press_g is None:
            return
        g = e.globalPosition().toPoint()
        if abs(g.y() - self._press_g.y()) > self.DRAG_THRESHOLD:
            self._moved = True
        self.host.do_v_move(g)

    def mouseReleaseEvent(self, e):  # noqa: N802
        self.host.end_v_move()
        if not self._moved:           # 거의 안 움직였으면 클릭 → 펼치기
            self.host.set_collapsed(False)
        self._press_g = None

    def paintEvent(self, e):  # noqa: N802
        super().paintEvent(e)          # 스타일시트 배경(둥근 탭)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        # 상단 아이콘
        iw = self._icon.width() / self._icon.devicePixelRatio()
        p.drawPixmap(int((self.width() - iw) / 2), 10, self._icon)
        # 세로 회전 텍스트 "엑셀 헬프"
        p.translate(self.width() / 2, self.height() / 2 + 12)
        p.rotate(90)
        f = QFont(self.font()); f.setPointSize(9); f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRect(-44, -10, 88, 20), int(Qt.AlignmentFlag.AlignCenter), "엑셀 헬프")
        p.end()


class GripBar(QFrame):
    """바닥 높이 조절 그립."""

    def __init__(self, host: "ExcelHelperWidget"):
        super().__init__(host)
        self.host = host
        self.setObjectName("grip")
        self.setFixedHeight(GRIP_H)
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.host.begin_resize(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.host.do_resize(e.globalPosition().toPoint())


class WidthGrip(QFrame):
    """안쪽 가장자리의 가로폭 조절 그립(수동 배치 오버레이)."""

    def __init__(self, host: "ExcelHelperWidget"):
        super().__init__(host)
        self.host = host
        self.setObjectName("wgrip")
        self.setFixedWidth(WGRIP_W)
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def mouseMoveEvent(self, e):  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.host.do_h_resize(e.globalPosition().toPoint())


class ExcelHelperWidget(QWidget):
    """좌/우 가장자리에 고정되는 사이드바 메인 윈도우."""

    def __init__(self, items: list[Item], settings: Settings):
        super().__init__()
        self.items = items
        self.settings = settings
        self.cards: list[ResultCard] = []
        self._section_headers: list[QWidget] = []
        self.selected_index = -1

        # id → item / name 조회용 (related 링크·핫리로드에서 사용)
        self._item_by_id = {i.id: i for i in items}
        self._name_of = {i.id: i.name for i in items}

        self.side = "right"
        self.collapsed = False
        self.user_y = TOP_MARGIN
        self.user_width = DEFAULT_WIDTH
        self.user_height = DEFAULT_HEIGHT
        self._move_off = 0
        self._resize_start = (0, 0)

        # 핫리로드
        self._data_path = paths.data_file()
        self._reloader = None  # main.py 가 주입(참조 유지 + 종료 정리)
        self._reload_debounce = QTimer(self)
        self._reload_debounce.setSingleShot(True)
        self._reload_debounce.setInterval(RELOAD_DEBOUNCE_MS)
        self._reload_debounce.timeout.connect(self.reload_data_now)

        self.setWindowTitle("엑셀 헬프 위젯")

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_search)

        self._build()
        self._apply_settings()
        self._run_search()
        self._apply_mode()

    # ----------------------------------------------------------------- UI
    def _build(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = TitleBar(self)
        root.addWidget(self.titlebar)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(10, 8, 10, 0)
        body.setSpacing(8)

        self.search_box = SearchLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("무엇을 하고 싶나요?  예: 중복, 값 찾기, 조건 합계")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.addAction(
            icons.icon("search", "#888", 18), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search_box.textChanged.connect(lambda _: self._debounce.start())
        self.search_box.upPressed.connect(lambda: self._move_selection(-1))
        self.search_box.downPressed.connect(lambda: self._move_selection(1))
        self.search_box.enterPressed.connect(self._toggle_selected)
        self.search_box.escPressed.connect(self._on_escape)
        self.search_box.copyPressed.connect(self._copy_selected)
        body.addWidget(self.search_box)

        chip_host = QWidget()
        chip_flow = FlowLayout(chip_host, spacing=4)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        for label in [ALL_CHIP, *CATEGORIES]:
            chip = QPushButton(label)
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            chip.clicked.connect(self._run_search)
            self.chip_group.addButton(chip)
            chip_flow.addWidget(chip)

        # 즐겨찾기 칩(카테고리 아님 — 단일 선택 그룹에 포함, 별도 처리)
        self.fav_chip = QPushButton(FAV_LABEL)
        self.fav_chip.setObjectName("chip")
        self.fav_chip.setCheckable(True)
        self.fav_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.fav_chip.setIcon(icons.icon("star_fill1", "#f5a623", 14))
        self.fav_chip.clicked.connect(self._run_search)
        self.chip_group.addButton(self.fav_chip)
        chip_flow.addWidget(self.fav_chip)

        body.addWidget(chip_host)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_host)
        body.addWidget(self.scroll, 1)

        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        body.addWidget(self.status)

        self.grip = GripBar(self)
        body.addWidget(self.grip)

        root.addWidget(self.body, 1)

        self.collapsed_tab = CollapsedTab(self)
        root.addWidget(self.collapsed_tab, 1)

        # 가로폭 그립(레이아웃 밖, 수동 배치 오버레이)
        self.width_grip = WidthGrip(self)

        self.toast = Toast(self)
        self._apply_style()

    def _current_category(self) -> str:
        btn = self.chip_group.checkedButton()
        return btn.text() if btn else ALL_CHIP

    def _fav_mode(self) -> bool:
        return self.chip_group.checkedButton() is self.fav_chip

    def _items_by_ids(self, ids) -> list[Item]:
        """id 리스트를 순서 유지하며 Item 으로(없는 id는 무시 — 방어)."""
        return [self._item_by_id[i] for i in ids if i in self._item_by_id]

    # ----------------------------------------------------------------- 검색/렌더
    def _run_search(self) -> None:
        query = self.search_box.text()
        if self._fav_mode():
            self.settings.set("category", FAV_LABEL)
            fav_items = self._items_by_ids(self.settings.get_list("favorites"))
            results = search.search(fav_items, query, ALL_CHIP)
            self._render([(None, results)], query, fav=True,
                         fav_empty=not fav_items)
            return

        category = self._current_category()
        self.settings.set("category", category)
        results = search.search(self.items, query, category)

        if not query.strip() and category == ALL_CHIP:
            recent = self._items_by_ids(self.settings.get_list("recent"))
            if recent:
                self._render([(RECENT_TITLE, recent), (ALL_TITLE, results)], query)
                return
        self._render([(None, results)], query)

    def _make_card(self, item: Item) -> ResultCard:
        card = ResultCard(
            item, self.list_host,
            is_favorite=self.settings.is_favorite(item.id),
            name_of=self._name_of,
        )
        card.copyRequested.connect(self._copy_text)
        card.activated.connect(self._on_card_activated)
        card.favoriteToggled.connect(self._on_favorite_toggled)
        card.relatedClicked.connect(self._jump_to)
        card.toggled.connect(lambda c=card: self._on_card_toggled(c))
        return card

    def _section_header(self, title: str) -> QLabel:
        h = QLabel(title)
        h.setObjectName("sectionHeader")
        return h

    def _clear_list(self) -> None:
        for w in (*self.cards, *self._section_headers):
            w.setParent(None)
            w.deleteLater()
        self.cards = []
        self._section_headers = []
        self.selected_index = -1

    def _render(self, sections, query: str, *, fav: bool = False,
                fav_empty: bool = False) -> None:
        """sections: [(title|None, [Item, ...]), ...] 순서대로 렌더."""
        self._clear_list()
        total = 0
        for title, items in sections:
            if not items:
                continue
            if title:
                hdr = self._section_header(title)
                self.list_layout.insertWidget(self.list_layout.count() - 1, hdr)
                self._section_headers.append(hdr)
            for item in items:
                card = self._make_card(item)
                self.list_layout.insertWidget(self.list_layout.count() - 1, card)
                self.cards.append(card)
                total += 1

        # 상태 문구
        if fav and fav_empty:
            self.status.setText("아직 즐겨찾기가 없어요. 카드의 ★를 눌러 추가하세요.")
        elif total == 0:
            if query.strip():
                self.status.setText(
                    "결과가 없어요. 다른 키워드로 검색해보세요.\n"
                    "예: '중복' → 중복 제거, '값찾기' → XLOOKUP, '조건 합계' → SUMIF"
                )
            elif fav:
                self.status.setText("즐겨찾기에서 검색 결과가 없어요.")
            else:
                self.status.setText("항목이 없습니다.")
        elif fav:
            self.status.setText(f"즐겨찾기 {total}개")
        elif not query.strip():
            self.status.setText(f"전체 {len(self.items)}개 · 키워드로 검색해보세요")
        else:
            self.status.setText(f"{total}개 결과")

        if self.cards:
            self._set_selection(0)

    # ----------------------------------------------------------------- 즐겨찾기/최근/related
    def _on_favorite_toggled(self, item_id: str, state: bool) -> None:
        self.settings.set_favorite(item_id, state)
        self.settings.save()

    def _on_card_toggled(self, card: ResultCard) -> None:
        # 펼칠 때만 최근 기록 갱신(접힘은 무시). 재렌더하지 않아 화면이 흔들리지 않음.
        if card.is_expanded():
            self.settings.add_recent(card.item.id)
            self.settings.save()

    def _jump_to(self, item_id: str) -> None:
        """related 링크 클릭 → 그 항목으로 검색 재실행 후 선택·펼침."""
        item = self._item_by_id.get(item_id)
        if item is None:
            return
        # '전체' 칩으로 되돌려 대상이 확실히 보이게 한 뒤, 이름으로 검색
        for btn in self.chip_group.buttons():
            if btn.text() == ALL_CHIP:
                btn.setChecked(True)
                break
        self.search_box.blockSignals(True)
        self.search_box.setText(item.name)
        self.search_box.blockSignals(False)
        self._run_search()
        for i, c in enumerate(self.cards):
            if c.item.id == item_id:
                self._set_selection(i)
                c.set_expanded(True)
                break

    # ----------------------------------------------------------------- 키보드 네비
    def _move_selection(self, delta: int) -> None:
        if not self.cards:
            return
        idx = max(0, min(len(self.cards) - 1, self.selected_index + delta))
        self._set_selection(idx)

    def _set_selection(self, idx: int) -> None:
        for i, card in enumerate(self.cards):
            card.set_selected(i == idx)
        self.selected_index = idx
        if 0 <= idx < len(self.cards):
            self.scroll.ensureWidgetVisible(self.cards[idx], 0, 20)

    def _on_card_activated(self, card: ResultCard) -> None:
        if card in self.cards:
            self._set_selection(self.cards.index(card))

    def _toggle_selected(self) -> None:
        if 0 <= self.selected_index < len(self.cards):
            self.cards[self.selected_index].toggle()

    def _copy_selected(self) -> None:
        if 0 <= self.selected_index < len(self.cards):
            if not self.cards[self.selected_index].copy_example():
                self.toast.show_message("복사할 예시가 없어요")

    def _on_escape(self) -> None:
        if self.search_box.text():
            self.search_box.clear()
        else:
            self.hide_to_tray()

    # ----------------------------------------------------------------- 복사
    def _copy_text(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.toast.show_message("복사됨")

    # ----------------------------------------------------------------- 창 동작
    def set_opacity(self, value: float) -> None:
        value = max(0.85, min(1.0, value))
        self.setWindowOpacity(value)
        self.settings.set("opacity", value)
        self.titlebar.opacity.blockSignals(True)
        self.titlebar.opacity.setValue(round(value * 100))
        self.titlebar.opacity.blockSignals(False)

    def _work_area(self):
        center = self.frameGeometry().center()
        screen = (
            QGuiApplication.screenAt(center)
            or self.screen()
            or QGuiApplication.primaryScreen()
        )
        return screen.availableGeometry()

    def _apply_mode(self) -> None:
        expanded = not self.collapsed
        self.titlebar.setVisible(expanded)
        self.body.setVisible(expanded)
        self.width_grip.setVisible(expanded)
        self.collapsed_tab.setVisible(self.collapsed)
        self.titlebar.refresh_glyphs(self.side)
        self.collapsed_tab.refresh_glyphs(self.side)
        self._apply_edge_geometry()

    def _apply_edge_geometry(self) -> None:
        """폭/높이를 상태에 따라 직접 정하고 항상 좌/우 가장자리에 붙인다."""
        wa = self._work_area()
        if self.collapsed:
            width, height = COLLAPSED_WIDTH, COLLAPSED_HEIGHT
        else:
            width = max(MIN_WIDTH, min(self.user_width, MAX_WIDTH, wa.width()))
            height = max(MIN_HEIGHT, min(self.user_height, wa.height()))
            self.user_width = width
            self.user_height = height
        y = max(wa.top(), min(self.user_y, wa.bottom() - height + 1))
        x = wa.left() if self.side == "left" else wa.right() - width + 1
        self.user_y = y
        self.setFixedWidth(width)
        self.setMinimumHeight(min(MIN_HEIGHT, height))
        self.setGeometry(x, y, width, height)
        self._position_overlays()

    def _position_overlays(self) -> None:
        """가로폭 그립을 안쪽 가장자리에 배치."""
        if self.collapsed:
            return
        gx = 0 if self.side == "right" else self.width() - WGRIP_W
        self.width_grip.setGeometry(gx, self.titlebar.height(),
                                    WGRIP_W, self.height() - self.titlebar.height())
        self.width_grip.raise_()

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        self._position_overlays()

    def set_side(self, side: str) -> None:
        if side not in ("left", "right"):
            return
        self.side = side
        self.settings.set("side", side)
        self.titlebar.refresh_glyphs(side)
        self.collapsed_tab.refresh_glyphs(side)
        self._apply_edge_geometry()

    def toggle_side(self) -> None:
        self.set_side("left" if self.side == "right" else "right")

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = bool(collapsed)
        self.settings.set("collapsed", self.collapsed)
        self._apply_mode()
        if not self.collapsed:
            self.raise_()
            self.activateWindow()
            self.search_box.setFocus()
            self.search_box.selectAll()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self.collapsed)

    # 세로 이동(가로 고정)
    def begin_v_move(self, gpos: QPoint) -> None:
        self._move_off = gpos.y() - self.y()

    def do_v_move(self, gpos: QPoint) -> None:
        wa = self._work_area()
        new_y = max(wa.top(), min(gpos.y() - self._move_off, wa.bottom() - self.height() + 1))
        self.user_y = new_y
        self.move(self.x(), new_y)

    def end_v_move(self) -> None:
        self._apply_edge_geometry()

    # 높이 조절
    def begin_resize(self, gpos: QPoint) -> None:
        self._resize_start = (gpos.y(), self.height())

    def do_resize(self, gpos: QPoint) -> None:
        wa = self._work_area()
        start_y, start_h = self._resize_start
        new_h = max(MIN_HEIGHT, min(start_h + (gpos.y() - start_y), wa.bottom() - self.y() + 1))
        self.user_height = new_h
        self.setFixedWidth(self.width())
        self.resize(self.width(), new_h)
        self._position_overlays()

    # 가로폭 조절(바깥 가장자리 고정, 안쪽만 이동)
    def do_h_resize(self, gpos: QPoint) -> None:
        wa = self._work_area()
        max_w = min(MAX_WIDTH, wa.width())
        if self.side == "right":
            right = self.x() + self.width()
            new_w = max(MIN_WIDTH, min(right - gpos.x(), max_w))
            new_x = right - new_w
        else:
            new_w = max(MIN_WIDTH, min(gpos.x() - self.x(), max_w))
            new_x = self.x()
        self.user_width = new_w
        self.setFixedWidth(new_w)
        self.move(new_x, self.y())
        self._position_overlays()

    # ----------------------------------------------------------------- 표시/숨김
    def show_and_focus(self) -> None:
        self.show()
        self._apply_edge_geometry()
        self.raise_()
        self.activateWindow()
        if not self.collapsed:
            self.search_box.setFocus()
            self.search_box.selectAll()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide_to_tray()
        else:
            self.show_and_focus()

    def hide_to_tray(self) -> None:
        self._persist_geometry()
        self.settings.save()
        self.hide()

    # ----------------------------------------------------------------- 핫리로드
    def schedule_reload(self) -> None:
        """watchdog 콜백(다른 스레드)에서 시그널로 호출 → 메인 스레드 디바운스."""
        self._reload_debounce.start(RELOAD_DEBOUNCE_MS)

    def reload_data_now(self) -> None:
        """수동/디바운스 후 리로드 진입점. 실패 시 재시도 후 폴백."""
        self._attempt_reload(RELOAD_RETRIES)

    def _attempt_reload(self, tries_left: int) -> None:
        try:
            new_items = load_items(self._data_path)
        except DataError:
            if tries_left > 0:
                # 저장 도중 읽기 경합 가능 → 잠시 후 재시도
                QTimer.singleShot(200, lambda: self._attempt_reload(tries_left - 1))
            else:
                # 검증 실패 폴백: 기존 데이터 유지 + 토스트
                self.toast.show_message("데이터 파일을 읽지 못했어요 — 기존 데이터 유지")
            return
        self._apply_reloaded(new_items)

    def _apply_reloaded(self, new_items: list[Item]) -> None:
        """데이터만 교체하고 현재 검색어·카테고리·선택을 보존해 재렌더."""
        prev_id = (self.cards[self.selected_index].item.id
                   if 0 <= self.selected_index < len(self.cards) else None)
        self.items = new_items
        self._item_by_id = {i.id: i for i in new_items}
        self._name_of = {i.id: i.name for i in new_items}
        self._run_search()  # 검색어/칩 그대로 → 같은 화면으로 다시 렌더
        if prev_id is not None:
            for i, c in enumerate(self.cards):
                if c.item.id == prev_id:
                    self._set_selection(i)
                    break
        self.toast.show_message(f"데이터 갱신됨 ({len(new_items)}개)")

    def shutdown(self) -> None:
        """종료 시 watchdog Observer 정리."""
        if self._reloader is not None:
            try:
                self._reloader.stop()
            except Exception:
                pass
            self._reloader = None

    # ----------------------------------------------------------------- 영속
    def _persist_geometry(self) -> None:
        self.settings.set("side", self.side)
        self.settings.set("collapsed", self.collapsed)
        self.settings.set("win_y", self.user_y)
        self.settings.set("win_width", self.user_width)
        self.settings.set("win_height", self.user_height)

    def _apply_settings(self) -> None:
        self.side = "left" if self.settings.get("side") == "left" else "right"
        self.collapsed = bool(self.settings.get("collapsed"))
        self.user_y = _as_int(self.settings.get("win_y"), TOP_MARGIN)
        self.user_width = _as_int(self.settings.get("win_width"), DEFAULT_WIDTH)
        self.user_height = _as_int(self.settings.get("win_height"), DEFAULT_HEIGHT)

        self.set_opacity(float(self.settings.get("opacity") or 1.0))

        cat = self.settings.get("category") or ALL_CHIP
        for btn in self.chip_group.buttons():
            if btn.text() == cat:
                btn.setChecked(True)
                break
        else:
            self.chip_group.buttons()[0].setChecked(True)

    def closeEvent(self, e):  # noqa: N802
        e.ignore()
        self.hide_to_tray()

    # ----------------------------------------------------------------- 스타일
    def _apply_style(self) -> None:
        self.setStyleSheet(
            "QWidget { font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; }"
            "ExcelHelperWidget { background:#f5f6f8; }"
            f"#titlebar {{ background:{EXCEL_GREEN}; }}"
            "#titleText { color:white; font-weight:bold; font-size:13px; }"
            "#iconBtn { background:transparent; border:none; }"
            "#iconBtn:hover { background:rgba(255,255,255,0.22); border-radius:4px; }"
            "#searchBox { padding:8px 10px; border:1px solid #cfcfcf;"
            " border-radius:8px; font-size:13px; background:white; }"
            f"#searchBox:focus {{ border:1px solid {EXCEL_GREEN}; }}"
            "#chip { padding:4px 10px; border:1px solid #cfcfcf; border-radius:12px;"
            " background:white; font-size:11px; }"
            f"#chip:checked {{ background:{EXCEL_GREEN}; color:white;"
            f" border:1px solid {EXCEL_GREEN}; }}"
            "#status { color:#888; font-size:11px; }"
            "#sectionHeader { color:#2e7d32; font-size:11px; font-weight:bold;"
            " padding:2px 2px 0 2px; }"
            "#grip { background:transparent; }"
            f"#grip:hover {{ background:rgba(46,125,50,0.25); }}"
            "#wgrip { background:transparent; }"
            f"#wgrip:hover {{ background:rgba(46,125,50,0.25); }}"
        )


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
