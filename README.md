# 엑셀 헬프 위젯 (Excel Helper Widget)

엑셀로 작업하다 막힐 때, 기능 **이름을 몰라도** "중복", "값 찾기", "조건 합계" 같은
**목적 키워드**로 검색해 함수·데이터 도구·피벗·조건부 서식·단축키를 바로 찾고
예시 수식을 복사하는 항상-위(always-on-top) 데스크톱 위젯입니다.

> 현재 상태: **P1 + P2 완료 + 콘텐츠 161개** (함수 102 / 데이터 도구 18 / 피벗 8 / 조건부 서식 9 / 단축키 24).
> P2: 즐겨찾기·최근 본 항목 / related 링크 점프 / JSON 핫리로드(파일 수정 자동 반영).

## 빠른 시작 (uv)

```powershell
uv sync                 # 의존성 설치 (PyQt6, pynput)
uv run python main.py   # 실행
```

개발용(테스트 포함):

```powershell
uv sync --extra dev
$env:QT_QPA_PLATFORM = "offscreen"   # 헤드리스 GUI 테스트용
uv run pytest -q
```

## 사용법

| 동작 | 방법 |
|---|---|
| 위젯 표시/숨김 | 글로벌 단축키 **Ctrl+Shift+E** (어디서나) 또는 트레이 아이콘 클릭 |
| 검색 | 검색창에 목적 키워드 입력 (입력 즉시 검색, 엔터 불필요) |
| 카테고리 필터 | 칩 클릭 — 검색어와 **AND** 로 동작 |
| 카드 펼침/접힘 | 카드 클릭 또는 **Enter** |
| 결과 이동 | **↑ / ↓** |
| 예시 복사 | 복사 아이콘 또는 선택 항목에서 **Ctrl+C** → "복사됨" 토스트 |
| 즐겨찾기 | 카드의 **★** 토글 → "⭐ 즐겨찾기" 칩으로 모아 보기(검색어와 AND) |
| 최근 본 항목 | 카드를 펼치면 기록 → 빈 검색·전체일 때 상단 "최근 본 항목" 섹션 |
| 관련 기능 이동 | 펼친 카드의 **관련** 링크 클릭 → 그 항목으로 검색·선택·펼침 |
| 데이터 자동 반영 | `excel_functions.json` 수정 시 재시작 없이 반영(트레이 "데이터 다시 읽기"로 수동도 가능) |
| 좌/우 가장자리 전환 | **시스템 트레이 메뉴 "왼쪽 ↔ 오른쪽 전환"** 에서만 |
| 접기 / 펼치기 | 타이틀바 접기 버튼 → 작은 **인덱스 탭**으로 접힘 / 탭을 클릭하면 펼침 |
| 세로 위치 이동 | 타이틀바(또는 접힌 탭) 드래그 — 가로는 항상 가장자리에 고정 |
| 높이 조절 | 사이드바 **맨 아래 가장자리** 드래그 |
| 가로폭 조절 | 사이드바 **안쪽 세로 가장자리** 드래그(바깥 가장자리는 고정) |
| 검색어 비우기 / 숨기기 | **Esc** (검색어 있으면 비우기, 없으면 트레이로 숨김) |
| 닫기(X) | 종료가 아니라 트레이로 숨김. **종료는 트레이 메뉴에서만** |

**사이드바 동작:** 위젯은 항상 화면 왼쪽 또는 오른쪽 **가장자리에 붙어** 있습니다(가장자리에서 떨어지지 않음). 좌/우 전환·접힘·세로 위치·가로폭·높이·투명도·마지막 카테고리는 종료 후에도 유지됩니다 (`%APPDATA%/ExcelHelperWidget/settings.json`). 아이콘은 모두 Google Material Symbols(`resources/icons/*.svg`)를 사용합니다.

## 구조

```
main.py                  # 진입점, 트레이/핫키 부트스트랩, 단일 인스턴스 잠금, 고DPI
app/
├── widget.py            # 메인 윈도우, 가장자리 고정 사이드바(접기/전환/리사이즈), 키보드 네비
├── search.py            # 데이터 로드 + 검색/정렬/가중치
├── result_card.py       # 결과 카드(펼침/복사)
├── tray.py              # 시스템 트레이 + 글로벌 단축키 + 좌/우 전환 메뉴
├── settings.py          # 창 상태(side/collapsed/위치/폭/높이/투명도/카테고리) 영속
├── toast.py             # 복사 토스트
├── icons.py             # Google Material Symbols(SVG) 아이콘 로더
├── reloader.py          # watchdog 파일 감시 → 메인 스레드 시그널(JSON 핫리로드)
└── paths.py             # 데이터/리소스 경로 (PyInstaller _MEIPASS 분기)
data/excel_functions.json # 기능 콘텐츠 161개 (앱과 분리 — 이 파일만 고치면 콘텐츠 갱신)
resources/icons/*.svg    # Google Material Symbols 아이콘
tests/                   # 검색·데이터·GUI/트레이 스모크 테스트 (pytest)
```

## 콘텐츠 추가/수정

코드 수정 없이 `data/excel_functions.json` 만 편집하면 됩니다. 스키마는
`excel-helper-widget-spec.md` §5 참고. 필수 필드(`id`/`name`/`category`/`purpose`/
`purpose_tags`/`syntax`)·카테고리 값·id 중복·`related` 참조 무결성은 앱 로드 시
검증되며, `tests/test_search.py` 가 같은 규칙을 자동 확인합니다.

> **검색이 전부입니다.** 사용자는 기능 이름을 모르고 들어오므로 `purpose_tags` 에
> 동의어·오타·한영 표기·구어체를 넉넉히 넣을수록 체감 품질이 올라갑니다.

## 패키징 (Windows 단일 exe)

```powershell
uv run pyinstaller --onefile --windowed `
  --add-data "data;data" --add-data "resources;resources" `
  --hidden-import watchdog.observers.read_directory_changes main.py
```

`data/excel_functions.json` 은 exe 옆에 함께 두면 외부에서 수정 가능합니다
(번들 내부 경로와 외부 경로를 모두 탐색 — `app/paths.py`). 핫리로드는 이 외부 파일을 감시합니다.

> **빌드 검증 완료(PyInstaller 6.20):** 단일 exe(약 35MB) 빌드 성공, 실행 시 정상 표시,
> exe 옆 `data/excel_functions.json` 수정 → **핫리로드 자동 반영 확인**.
> watchdog 동적 import 는 PyInstaller 6.x + `pyinstaller-hooks-contrib` 가 자동 처리해
> `--hidden-import` 없이도 동작하지만, 구버전 대비 안전장치로 남겨둡니다(있어도 무해).

> **개발 환경 메모:** 프로젝트가 OneDrive 동기화 폴더에 있어 `.venv`를 OneDrive가 잠그면
> `uv sync`가 실패할 수 있습니다. 그 경우 venv를 동기화 밖에 두세요:
> `$env:UV_PROJECT_ENVIRONMENT = "C:\Users\<you>\.venvs\excel-helper"` 후 `uv sync`.

## 구현 범위

- **P1 (완료):** 좌/우 가장자리 고정 사이드바(좌우 전환·접기/펼치기 인덱스 탭·세로 이동·높이/가로폭 리사이즈)·항상 위 /
  트레이 + 글로벌 핫키 + 단일 인스턴스 잠금 / 통합 검색 + 카테고리 칩 / 카드 펼침·복사·토스트 /
  키보드 네비 / 투명도·창 상태 영속 / Google Material 아이콘 / 고DPI 대응 / 콘텐츠 161개
- **P2 (완료):** 즐겨찾기(★ 토글 + 칩 필터) / 최근 본 항목(LRU, 빈 상태 섹션) /
  `related` 링크 점프 / JSON 핫리로드(watchdog 자동 감시 + 디바운스 + 깨진 JSON 폴백 + 수동 새로고침) —
  저장은 SQLite 없이 `settings.json` 사용
- **P3 (예정):** 사용자 메모, 하단 가로 도킹, 파워 쿼리 콘텐츠
