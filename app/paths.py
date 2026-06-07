"""리소스/데이터 경로 해석.

PyInstaller --onefile 로 패키징하면 번들 내부(``sys._MEIPASS``)에 데이터가 들어가지만,
스펙상 ``data/excel_functions.json`` 은 exe 옆에서도 수정 가능해야 한다.
→ exe 옆(외부) 경로를 우선 탐색하고, 없으면 번들 내부 경로로 폴백한다.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bundle_dir() -> Path:
    """PyInstaller 번들 내부 경로(_MEIPASS) 또는 소스 루트."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    # app/paths.py → 프로젝트 루트
    return Path(__file__).resolve().parent.parent


def _external_dir() -> Path:
    """실행 파일(exe) 또는 스크립트가 위치한 디렉터리."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_file(name: str = "excel_functions.json") -> Path:
    """데이터 JSON 경로. 외부(exe 옆) 우선, 없으면 번들 내부."""
    external = _external_dir() / "data" / name
    if external.is_file():
        return external
    return _bundle_dir() / "data" / name


def resource_dir() -> Path:
    """resources 디렉터리(아이콘 등). 외부 우선, 없으면 번들 내부."""
    external = _external_dir() / "resources"
    if external.is_dir():
        return external
    return _bundle_dir() / "resources"
