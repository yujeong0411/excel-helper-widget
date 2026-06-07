"""검색 로직 + 데이터 로드 단위 테스트."""

from __future__ import annotations

import json

import pytest

from app import paths, search
from app.search import ALL_CHIP, CATEGORIES, DataError, Item, load_items


@pytest.fixture(scope="module")
def items() -> list[Item]:
    return load_items(paths.data_file())


# ---------------------------------------------------------------- 데이터 로드/무결성


def test_real_data_loads(items):
    assert len(items) >= 30, "P1 샘플 데이터가 충분히 로드되어야 함"


def test_all_categories_present(items):
    cats = {i.category for i in items}
    for c in CATEGORIES:
        assert c in cats, f"카테고리 누락: {c}"


def test_ids_unique(items):
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))


def test_examples_present_for_functions(items):
    # 함수 카테고리는 대부분 예시 수식이 있어야 복사 기능이 의미가 있음
    funcs = [i for i in items if i.category == "함수"]
    with_example = [i for i in funcs if i.example]
    assert len(with_example) / len(funcs) >= 0.8


def test_related_ids_resolve(items):
    ids = {i.id for i in items}
    for i in items:
        for rid in i.related:
            assert rid in ids, f"{i.id} 의 related 가 존재하지 않는 id 를 가리킴: {rid}"


# ---------------------------------------------------------------- 스키마 검증 실패 케이스


def _write(tmp_path, data):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_missing_required_field(tmp_path):
    bad = [{"id": "x", "name": "X", "category": "함수", "purpose": "p"}]  # tags/syntax 누락
    with pytest.raises(DataError):
        load_items(_write(tmp_path, bad))


def test_bad_category(tmp_path):
    bad = [{
        "id": "x", "name": "X", "category": "없는카테고리",
        "purpose": "p", "purpose_tags": ["t"], "syntax": "s",
    }]
    with pytest.raises(DataError):
        load_items(_write(tmp_path, bad))


def test_duplicate_id(tmp_path):
    one = {
        "id": "x", "name": "X", "category": "함수",
        "purpose": "p", "purpose_tags": ["t"], "syntax": "s",
    }
    with pytest.raises(DataError):
        load_items(_write(tmp_path, [one, dict(one)]))


def test_not_a_list(tmp_path):
    with pytest.raises(DataError):
        load_items(_write(tmp_path, {"id": "x"}))


def test_missing_file(tmp_path):
    with pytest.raises(DataError):
        load_items(tmp_path / "nope.json")


# ---------------------------------------------------------------- 검색 동작


def _names(results):
    return [r.name for r in results]


def test_empty_query_returns_all_sorted(items):
    res = search.search(items, "")
    assert len(res) == len(items)
    assert _names(res) == sorted(_names(res), key=str.lower)


def test_category_filter_only(items):
    res = search.search(items, "", category="피벗")
    assert res and all(i.category == "피벗" for i in res)


def test_synonym_korean_hits_vlookup(items):
    # 이름을 몰라도 '값찾기' 같은 목적 키워드로 찾혀야 함
    res = search.search(items, "값찾기")
    ids = {i.id for i in res}
    assert {"xlookup", "vlookup", "index_match"} & ids


def test_duplicate_keyword(items):
    res = search.search(items, "중복")
    ids = {i.id for i in res}
    assert "remove_duplicates" in ids
    assert "unique" in ids


def test_name_exact_ranks_first(items):
    res = search.search(items, "XLOOKUP")
    assert res[0].id == "xlookup"


def test_case_insensitive(items):
    lo = search.search(items, "xlookup")
    hi = search.search(items, "XLOOKUP")
    assert _names(lo) == _names(hi)


def test_multi_token_and(items):
    # '조건 합계' → 두 토큰 모두 매칭(SUMIF)
    res = search.search(items, "조건 합계")
    assert res, "두 토큰 AND 매칭 결과가 있어야 함"
    assert res[0].id == "sumif"


def test_multi_token_requires_all(items):
    # 서로 절대 함께 안 나오는 토큰 조합 → 결과 없음
    res = search.search(items, "xlookup 슬라이서")
    assert res == []


def test_category_and_query_and(items):
    # '함수' 칩 + '날짜' → 날짜 관련 함수만
    res = search.search(items, "날짜", category="함수")
    assert res and all(i.category == "함수" for i in res)
    ids = {i.id for i in res}
    assert "today_now" in ids


def test_no_result(items):
    assert search.search(items, "존재하지않는키워드zzzz") == []


def test_tag_beats_purpose_ordering(items):
    # 'vlookup' 은 vlookup 항목의 태그/이름에 강하게 매칭 → 최상단
    res = search.search(items, "vlookup")
    assert res[0].id in {"vlookup", "xlookup"}
