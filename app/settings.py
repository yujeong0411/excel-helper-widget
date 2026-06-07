"""창 상태(위치/크기/투명도/핀) 영속.

QSettings 대신 사람이 읽고 고치기 쉬운 JSON 파일을 사용한다.
저장 위치: %APPDATA%/ExcelHelperWidget/settings.json (없으면 홈 폴더 하위).
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

APP_DIR_NAME = "ExcelHelperWidget"

RECENT_MAX = 15

DEFAULTS: dict = {
    "side": "right",         # 사이드바 부착 가장자리: "left" | "right"
    "collapsed": False,      # 접힘 상태
    "win_y": None,           # 세로 위치(px)
    "win_width": None,       # 가로폭(px)
    "win_height": None,      # 높이(px)
    "opacity": 1.0,          # 0.85 ~ 1.0
    "category": "전체",       # 마지막 선택 칩
    "favorites": [],         # 즐겨찾기 항목 id (추가순)
    "recent": [],            # 최근 펼쳐 본 항목 id (LRU, 최신 앞)
}


def _config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / APP_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_path() -> Path:
    return _config_dir() / "settings.json"


class Settings:
    """단순 키-값 설정. load() 후 get/set, save() 로 디스크 반영."""

    def __init__(self, path: Path | None = None):
        self.path = path or _config_path()
        # deepcopy — favorites/recent 리스트가 DEFAULTS 와 공유되지 않도록
        self._data: dict = copy.deepcopy(DEFAULTS)

    def load(self) -> "Settings":
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._data.update({k: raw[k] for k in DEFAULTS if k in raw})
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass  # 처음 실행이거나 손상 → 기본값 유지
        return self

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass  # 저장 실패는 치명적이지 않음

    def get(self, key: str):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self._data[key] = value

    # ----------------------------------------------------------------- 리스트 헬퍼
    def get_list(self, key: str) -> list[str]:
        v = self._data.get(key)
        return list(v) if isinstance(v, list) else []

    def is_favorite(self, item_id: str) -> bool:
        return item_id in self.get_list("favorites")

    def toggle_favorite(self, item_id: str) -> bool:
        """즐겨찾기 추가/제거 후 새 상태(True=즐겨찾기됨) 반환."""
        favs = self.get_list("favorites")
        if item_id in favs:
            favs.remove(item_id)
            state = False
        else:
            favs.append(item_id)
            state = True
        self._data["favorites"] = favs
        return state

    def set_favorite(self, item_id: str, state: bool) -> None:
        favs = self.get_list("favorites")
        if state and item_id not in favs:
            favs.append(item_id)
        elif not state and item_id in favs:
            favs.remove(item_id)
        self._data["favorites"] = favs

    def add_recent(self, item_id: str, max_n: int = RECENT_MAX) -> None:
        """최근 본 항목 LRU 갱신: 기존 항목 제거 후 맨 앞으로, 최대 max_n 유지."""
        recent = self.get_list("recent")
        if item_id in recent:
            recent.remove(item_id)
        recent.insert(0, item_id)
        self._data["recent"] = recent[:max_n]
