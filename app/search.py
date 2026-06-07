"""검색 로직 + 데이터 로드.

스펙 §5 검색 로직:
- 검색어를 공백으로 토큰 분리, 각 토큰을 name / purpose / purpose_tags 에 부분 문자열 매칭
- 가중치: name 정확·접두 매칭 > purpose_tags 매칭 > purpose 매칭
- 대소문자 무시, 한/영/숫자 그대로 비교
- 카테고리 칩이 "전체"가 아니면 해당 category 로 1차 필터 후 검색
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# 칩 ↔ category 1:1 (스펙 §4.3 / 필드 정의)
CATEGORIES = ["함수", "데이터 도구", "피벗", "조건부 서식", "단축키"]
ALL_CHIP = "전체"

REQUIRED_FIELDS = ("id", "name", "category", "purpose", "purpose_tags", "syntax")

# 토큰별 매칭 점수 가중치
W_NAME_EXACT = 1000      # name 이 토큰과 정확히 일치
W_NAME_PREFIX = 500      # name 이 토큰으로 시작
W_NAME_SUBSTR = 200      # name 에 토큰 포함
W_TAG_EXACT = 120        # 태그 하나가 토큰과 정확히 일치
W_TAG_PREFIX = 80        # 태그가 토큰으로 시작
W_TAG_SUBSTR = 50        # 태그에 토큰 포함
W_PURPOSE_SUBSTR = 20    # purpose 에 토큰 포함


@dataclass(frozen=True)
class Item:
    """엑셀 기능 항목."""

    id: str
    name: str
    category: str
    purpose: str
    purpose_tags: tuple[str, ...]
    syntax: str
    subcategory: str | None = None
    example: str | None = None
    note: str | None = None
    shortcut: str | None = None
    related: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, raw: dict) -> "Item":
        return cls(
            id=raw["id"],
            name=raw["name"],
            category=raw["category"],
            purpose=raw["purpose"],
            purpose_tags=tuple(raw.get("purpose_tags") or ()),
            syntax=raw["syntax"],
            subcategory=raw.get("subcategory"),
            example=raw.get("example"),
            note=raw.get("note"),
            shortcut=raw.get("shortcut"),
            related=tuple(raw.get("related") or ()),
        )


class DataError(Exception):
    """데이터 파일 로드/검증 실패."""


def load_items(path: str | Path) -> list[Item]:
    """JSON 파일에서 항목 목록을 로드하고 스키마를 검증한다."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataError(f"데이터 파일을 찾을 수 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DataError(f"JSON 파싱 오류 ({path}): {exc}") from exc

    if not isinstance(raw, list):
        raise DataError("최상위 데이터는 항목 배열이어야 합니다.")

    items: list[Item] = []
    seen_ids: set[str] = set()
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise DataError(f"{idx}번째 항목이 객체가 아닙니다.")
        missing = [f for f in REQUIRED_FIELDS if not entry.get(f)]
        if missing:
            raise DataError(
                f"{idx}번째 항목(id={entry.get('id')!r})에 필수 필드 누락: {missing}"
            )
        if entry["category"] not in CATEGORIES:
            raise DataError(
                f"{idx}번째 항목(id={entry['id']!r})의 category 값이 올바르지 않음: "
                f"{entry['category']!r} (허용: {CATEGORIES})"
            )
        if entry["id"] in seen_ids:
            raise DataError(f"id 중복: {entry['id']!r}")
        seen_ids.add(entry["id"])
        items.append(Item.from_dict(entry))
    return items


def _tokenize(query: str) -> list[str]:
    return [t for t in query.lower().split() if t]


def _score_token(item: Item, token: str) -> int:
    """단일 토큰이 항목에 매칭되는 점수. 0 이면 미매칭."""
    name = item.name.lower()
    best = 0
    if name == token:
        best = max(best, W_NAME_EXACT)
    elif name.startswith(token):
        best = max(best, W_NAME_PREFIX)
    elif token in name:
        best = max(best, W_NAME_SUBSTR)

    for tag in item.purpose_tags:
        tl = tag.lower()
        if tl == token:
            best = max(best, W_TAG_EXACT)
        elif tl.startswith(token):
            best = max(best, W_TAG_PREFIX)
        elif token in tl:
            best = max(best, W_TAG_SUBSTR)

    if token in item.purpose.lower():
        best = max(best, W_PURPOSE_SUBSTR)
    return best


def score(item: Item, tokens: list[str]) -> int:
    """모든 토큰이 매칭돼야(AND) 점수 반환, 하나라도 미매칭이면 0."""
    total = 0
    for token in tokens:
        s = _score_token(item, token)
        if s == 0:
            return 0
        total += s
    return total


def search(
    items: list[Item],
    query: str,
    category: str = ALL_CHIP,
) -> list[Item]:
    """검색 실행.

    - category 가 "전체"가 아니면 해당 카테고리로 1차 필터
    - query 가 비면 (필터된) 전체를 이름순으로 반환
    - 그 외엔 점수 내림차순, 동점은 이름 오름차순 정렬
    """
    pool = items if category == ALL_CHIP else [i for i in items if i.category == category]

    tokens = _tokenize(query)
    if not tokens:
        return sorted(pool, key=lambda i: i.name.lower())

    scored = [(score(i, tokens), i) for i in pool]
    matched = [(s, i) for s, i in scored if s > 0]
    matched.sort(key=lambda si: (-si[0], si[1].name.lower()))
    return [i for _, i in matched]
