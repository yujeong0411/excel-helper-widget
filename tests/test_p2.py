"""P2 테스트 — 즐겨찾기/최근, related 점프, JSON 핫리로드."""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtWidgets import QApplication

from app import paths
from app.search import load_items
from app.settings import RECENT_MAX, Settings


# ---------------------------------------------------------------- settings 단위


def test_favorites_toggle_roundtrip(tmp_path):
    s = Settings(path=tmp_path / "s.json")
    assert s.get_list("favorites") == []
    assert s.toggle_favorite("xlookup") is True
    assert s.toggle_favorite("sumif") is True
    assert s.is_favorite("xlookup")
    assert s.toggle_favorite("xlookup") is False  # 제거
    assert not s.is_favorite("xlookup")
    s.save()
    again = Settings(path=s.path).load()
    assert again.get_list("favorites") == ["sumif"]


def test_recent_lru(tmp_path):
    s = Settings(path=tmp_path / "s.json")
    for i in range(RECENT_MAX + 5):
        s.add_recent(f"id{i}")
    rec = s.get_list("recent")
    assert len(rec) == RECENT_MAX           # 최대 N 유지
    assert rec[0] == f"id{RECENT_MAX + 4}"  # 최신이 앞
    # 중복은 앞으로 이동(LRU)
    s.add_recent("id20")
    assert s.get_list("recent")[0] == "id20"
    assert s.get_list("recent").count("id20") == 1


def test_settings_lists_not_shared(tmp_path):
    # deepcopy 로 인스턴스/DEFAULTS 간 리스트 공유 안 됨
    from app.settings import DEFAULTS
    a = Settings(path=tmp_path / "a.json")
    a.toggle_favorite("zzz")
    b = Settings(path=tmp_path / "b.json")
    assert b.get_list("favorites") == []
    assert DEFAULTS["favorites"] == []


# ---------------------------------------------------------------- 위젯 통합


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def widget(qapp, tmp_path):
    from app.widget import ExcelHelperWidget
    items = load_items(paths.data_file())
    s = Settings(path=tmp_path / "s.json")
    w = ExcelHelperWidget(items, s)
    yield w
    w.deleteLater()


def _select_chip(widget, text):
    for b in widget.chip_group.buttons():
        if b.text() == text:
            b.setChecked(True)
            return


def test_favorite_chip_filters_and_AND(widget):
    # xlookup, sumif 즐겨찾기
    widget.settings.set("favorites", ["xlookup", "sumif"])
    widget.fav_chip.setChecked(True)
    widget._run_search()
    ids = {c.item.id for c in widget.cards}
    assert ids == {"xlookup", "sumif"}
    # 즐겨찾기 + 검색어 AND
    widget.search_box.setText("xlookup")
    widget._run_search()
    ids = {c.item.id for c in widget.cards}
    assert ids == {"xlookup"}


def test_favorite_chip_empty_message(widget):
    widget.settings.set("favorites", [])
    widget.fav_chip.setChecked(True)
    widget._run_search()
    assert widget.cards == []
    assert "즐겨찾기가 없" in widget.status.text()


def test_favorite_toggle_persists(widget):
    card = widget.cards[0]
    cid = card.item.id
    card._on_star()  # 즐겨찾기 켜기
    assert widget.settings.is_favorite(cid)
    card._on_star()  # 끄기
    assert not widget.settings.is_favorite(cid)


def test_recent_updates_on_expand_and_section(widget):
    # 빈 검색 + 전체에서 시작 → recent 없음
    widget.search_box.setText("")
    _select_chip(widget, "전체")
    widget._run_search()
    # 어떤 카드를 펼치면 recent 앞으로
    target = widget.cards[3]
    tid = target.item.id
    target.set_expanded(True)
    assert widget.settings.get_list("recent")[0] == tid
    # 다시 빈 검색/전체로 렌더 → '최근 본 항목' 섹션 헤더 노출
    widget._run_search()
    titles = [h.text() for h in widget._section_headers]
    assert "최근 본 항목" in titles


def test_related_jump(widget):
    # XLOOKUP 카드 → related 에 index_match/vlookup 존재
    widget.search_box.setText("XLOOKUP")
    widget._run_search()
    assert widget.cards[0].item.id == "xlookup"
    widget._jump_to("index_match")
    # 검색어가 대상 name 으로 바뀌고 그 카드가 선택·펼침
    assert widget.search_box.text() == "INDEX + MATCH"
    sel = widget.cards[widget.selected_index]
    assert sel.item.id == "index_match"
    assert sel.is_expanded()


def test_missing_id_defense(widget):
    widget.settings.set("favorites", ["xlookup", "does_not_exist_zzz"])
    widget.fav_chip.setChecked(True)
    widget._run_search()  # 없는 id 는 조용히 무시, 크래시 없음
    ids = {c.item.id for c in widget.cards}
    assert ids == {"xlookup"}


# ---------------------------------------------------------------- 핫리로드


def _write_json(path, items):
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


def test_reload_applies_new_data(widget, tmp_path):
    data = tmp_path / "d.json"
    _write_json(data, [{
        "id": "only_one", "name": "단 하나", "category": "함수",
        "purpose": "테스트 항목", "purpose_tags": ["테스트"], "syntax": "=ONE()",
    }])
    widget._data_path = data
    # 현재 검색 상태(검색어/카테고리) 보존 확인용
    widget.search_box.setText("")
    _select_chip(widget, "전체")
    widget.reload_data_now()
    assert len(widget.items) == 1
    assert widget._item_by_id["only_one"].name == "단 하나"
    # 검색어/카테고리 보존
    assert widget.search_box.text() == ""


def test_reload_broken_json_keeps_old_data(widget, tmp_path):
    before = len(widget.items)
    widget.search_box.setText("값")
    widget._run_search()
    cards_before = [c.item.id for c in widget.cards]

    broken = tmp_path / "broken.json"
    broken.write_text("{ this is not valid json ", encoding="utf-8")
    widget._data_path = broken
    widget._attempt_reload(0)  # 재시도 없이 즉시 폴백

    assert len(widget.items) == before          # 기존 데이터 유지
    assert [c.item.id for c in widget.cards] == cards_before  # 검색 상태 보존


def test_reload_debounce_coalesces(widget):
    from PyQt6.QtTest import QTest
    from app.widget import RELOAD_DEBOUNCE_MS
    widget.schedule_reload()
    widget.schedule_reload()
    widget.schedule_reload()
    assert widget._reload_debounce.isActive()    # 1회만 대기
    QTest.qWait(RELOAD_DEBOUNCE_MS + 250)
    assert not widget._reload_debounce.isActive()  # 한 번 발화 후 종료
