"""GUI 스모크 테스트 — offscreen 플랫폼으로 위젯 동작 검증.

pytest-qt 없이 QApplication 을 직접 띄워 핵심 상호작용(검색 렌더, 선택 이동,
복사, 카테고리 칩, 카드 펼침)을 검증한다.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app import paths
from app.search import load_items
from app.settings import Settings


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def widget(qapp, tmp_path):
    from app.widget import ExcelHelperWidget

    items = load_items(paths.data_file())
    settings = Settings(path=tmp_path / "s.json")
    w = ExcelHelperWidget(items, settings)
    yield w
    w.deleteLater()


def test_initial_render_shows_all(widget):
    assert len(widget.cards) == len(widget.items)
    # 빈 검색 → 첫 카드가 선택됨
    assert widget.selected_index == 0


def test_search_filters(widget):
    widget.search_box.setText("중복")
    widget._run_search()
    names = [c.item.id for c in widget.cards]
    assert "remove_duplicates" in names
    assert "xlookup" not in names


def test_category_chip_filters(widget):
    for btn in widget.chip_group.buttons():
        if btn.text() == "피벗":
            btn.setChecked(True)
            break
    widget._run_search()
    assert widget.cards
    assert all(c.item.category == "피벗" for c in widget.cards)


def test_selection_moves_and_clamps(widget):
    widget.search_box.setText("")
    widget._run_search()
    widget._set_selection(0)
    widget._move_selection(-1)  # 위 경계
    assert widget.selected_index == 0
    widget._move_selection(1)
    assert widget.selected_index == 1
    # 끝으로 밀어도 범위 내
    for _ in range(1000):
        widget._move_selection(1)
    assert widget.selected_index == len(widget.cards) - 1


def test_copy_example_to_clipboard(widget, qapp):
    widget.search_box.setText("XLOOKUP")
    widget._run_search()
    assert widget.cards[0].item.id == "xlookup"
    widget._set_selection(0)
    widget._copy_selected()
    assert QApplication.clipboard().text() == widget.cards[0].item.example


def test_card_expand_collapse(widget):
    card = widget.cards[0]
    assert not card.is_expanded()
    card.toggle()
    assert card.is_expanded()
    card.toggle()
    assert not card.is_expanded()


def test_escape_clears_then_hides(widget):
    widget.search_box.setText("abc")
    widget._on_escape()
    assert widget.search_box.text() == ""  # 1차: 비우기


def test_no_result_status(widget):
    widget.search_box.setText("존재하지않는키워드zzzz")
    widget._run_search()
    assert widget.cards == []
    assert "다른 키워드" in widget.status.text()


def test_opacity_clamped(widget):
    # Qt 는 창 투명도를 8비트(1/255 ≈ 0.004)로 양자화하므로 그만큼 여유를 둔다.
    q = 1.0 / 255
    widget.set_opacity(0.5)
    assert widget.windowOpacity() >= 0.85 - q
    assert widget.settings.get("opacity") == 0.85  # 저장값은 정확히 클램프
    widget.set_opacity(2.0)
    assert widget.windowOpacity() <= 1.0 + 1e-9
    assert widget.settings.get("opacity") == 1.0


def test_default_sticks_to_right_edge(widget):
    widget.show_and_focus()
    wa = widget._work_area()
    assert widget.side == "right"
    assert abs(widget.frameGeometry().right() - wa.right()) <= 1


def test_toggle_side_to_left_edge(widget):
    widget.show_and_focus()
    widget.toggle_side()
    wa = widget._work_area()
    assert widget.side == "left"
    assert abs(widget.frameGeometry().left() - wa.left()) <= 1
    widget.toggle_side()
    assert widget.side == "right"
    assert abs(widget.frameGeometry().right() - widget._work_area().right()) <= 1


def test_collapse_changes_width_keeps_edge(widget):
    from app.widget import COLLAPSED_WIDTH, DEFAULT_WIDTH

    widget.show_and_focus()
    assert widget.width() == DEFAULT_WIDTH
    widget.set_collapsed(True)
    assert widget.collapsed
    assert widget.width() == COLLAPSED_WIDTH
    # 접혀도 오른쪽 가장자리 유지
    assert abs(widget.frameGeometry().right() - widget._work_area().right()) <= 1
    # 본문 숨김, 인덱스 탭 표시
    assert not widget.body.isVisible()
    assert widget.collapsed_tab.isVisible()
    widget.set_collapsed(False)
    assert widget.width() == DEFAULT_WIDTH
    assert widget.body.isVisible()


def test_width_resize_keeps_outer_edge(widget):
    from PyQt6.QtCore import QPoint
    from app.widget import MIN_WIDTH

    widget.show_and_focus()  # 우측 도킹
    right_before = widget.frameGeometry().right()
    # 안쪽(왼쪽) 가장자리를 왼쪽으로 끌어 폭 확대
    inner_x = widget.x()
    widget.do_h_resize(QPoint(inner_x - 120, widget.y() + 200))
    assert widget.width() > 360
    assert widget.width() <= 760
    # 바깥(오른쪽) 가장자리는 그대로
    assert abs(widget.frameGeometry().right() - right_before) <= 1
    assert widget.user_width == widget.width()
    # 최소폭 클램프
    widget.do_h_resize(QPoint(widget.x() + 9999, widget.y() + 200))
    assert widget.width() >= MIN_WIDTH


def test_collapse_left_keeps_left_edge(widget):
    widget.show_and_focus()
    widget.set_side("left")
    widget.set_collapsed(True)
    assert abs(widget.frameGeometry().left() - widget._work_area().left()) <= 1


def test_vertical_move_keeps_x(widget):
    widget.show_and_focus()
    x_before = widget.x()
    from PyQt6.QtCore import QPoint
    widget.begin_v_move(QPoint(widget.x() + 20, widget.y() + 10))
    widget.do_v_move(QPoint(widget.x() + 20, widget.y() + 120))  # 아래로 끌기
    assert widget.x() == x_before  # 가로는 그대로(가장자리 유지)


def test_always_on_top_flag_set(widget):
    assert bool(widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)


def test_settings_persist_roundtrip(widget, tmp_path):
    widget.show_and_focus()
    widget.set_opacity(0.9)
    widget.set_side("left")
    widget.set_collapsed(True)
    for btn in widget.chip_group.buttons():
        if btn.text() == "함수":
            btn.setChecked(True)
            break
    widget._run_search()
    widget.hide_to_tray()  # save

    reloaded = Settings(path=widget.settings.path).load()
    assert abs(float(reloaded.get("opacity")) - 0.9) < 1e-6
    assert reloaded.get("category") == "함수"
    assert reloaded.get("side") == "left"
    assert reloaded.get("collapsed") is True
    assert reloaded.get("win_height") is not None
    assert reloaded.get("win_width") is not None
