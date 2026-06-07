"""트레이 컨트롤러 테스트 — 메뉴 구성/액션 동작/종료."""

from __future__ import annotations

import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from app import paths
from app.search import load_items
from app.settings import DEFAULTS, Settings


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app


@pytest.fixture
def tray(qapp, tmp_path):
    from app.tray import TrayController
    from app.widget import ExcelHelperWidget

    st = Settings(path=tmp_path / "s.json")
    st._data = dict(DEFAULTS)
    w = ExcelHelperWidget(load_items(paths.data_file()), st)
    tc = TrayController(qapp, w)
    yield tc
    tc.tray.hide()
    w.deleteLater()


def test_menu_built_with_actions(tray):
    menu = tray.tray.contextMenu()
    assert menu is not None
    texts = [a.text() for a in menu.actions() if a.text()]
    assert any("표시" in t for t in texts)
    assert any("전환" in t for t in texts)  # 왼쪽↔오른쪽 전환 액션
    assert any("종료" in t for t in texts)


def test_menu_has_parent_widget(tray):
    # 부모 없는 QMenu 는 Windows 트레이에서 클릭이 안 먹는 문제가 있음
    assert tray.tray.contextMenu().parent() is tray.widget


def test_menu_survives_gc(tray):
    gc.collect()
    assert tray.tray.contextMenu() is not None
    assert len(tray.tray.contextMenu().actions()) >= 3


def test_controller_survives_gc_without_external_ref(qapp, tmp_path):
    """main.py 처럼 반환값을 저장하지 않아도 GC 후 컨트롤러와 액션이 살아있어야 함.
    (저장 안 하면 메뉴의 종료/도킹 슬롯이 죽어 클릭이 안 먹던 버그의 회귀 방지)"""
    import weakref

    from app.tray import TrayController
    from app.widget import ExcelHelperWidget

    st = Settings(path=tmp_path / "s2.json")
    st._data = dict(DEFAULTS)
    w = ExcelHelperWidget(load_items(paths.data_file()), st)
    ref = weakref.ref(TrayController(qapp, w))  # 반환값 미저장
    gc.collect()
    assert ref() is not None, "TrayController 가 GC 됨 — 메뉴 액션이 죽는다"
    # 좌우 전환 액션이 실제로 동작하는지까지 확인
    w.show_and_focus()
    [a for a in ref().tray.contextMenu().actions() if "전환" in a.text()][0].trigger()
    assert w.side == "left"
    assert abs(w.frameGeometry().left() - w._work_area().left()) <= 1
    ref().tray.hide(); w.deleteLater()


def test_side_toggle_action(tray):
    tray.widget.show_and_focus()
    assert tray.widget.side == "right"
    act = [a for a in tray.tray.contextMenu().actions() if "전환" in a.text()][0]
    act.trigger()
    assert tray.widget.side == "left"
    assert abs(tray.widget.frameGeometry().left() - tray.widget._work_area().left()) <= 1


def test_toggle_action_hides_visible_widget(tray):
    tray.widget.show()
    assert tray.widget.isVisible()
    show = [a for a in tray.tray.contextMenu().actions() if "표시" in a.text()][0]
    show.trigger()  # 보이는 상태 → 숨김
    assert not tray.widget.isVisible()


def test_quit_action_hides_tray_and_quits(tray, qapp):
    called = {"v": False}
    orig = qapp.quit
    qapp.quit = lambda: called.__setitem__("v", True)
    try:
        quit_act = [a for a in tray.tray.contextMenu().actions() if a.text() == "종료"][0]
        quit_act.trigger()
    finally:
        qapp.quit = orig
    assert called["v"] is True
    assert not tray.tray.isVisible()


def test_left_click_toggles(tray):
    tray.widget.show()
    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert not tray.widget.isVisible()
    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert tray.widget.isVisible()
