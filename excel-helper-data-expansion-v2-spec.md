# 엑셀 헬퍼 위젯 — 데이터 대확장(102 → 160+개) 구현 명세

> 작성자: 최유정 / 대상 에이전트: Claude Code / 우선순위: P1(콘텐츠)
> 작업 유형: 기능 추가(기존 데이터 유지 + 확장). 코드 변경 없이 `data/excel_functions.json`만 확장.

## 1. 개요와 목적

현재 데이터 102개를 첨부 자료(엑셀 함수 정리 목록, 단축키 모음)를 참고해 **최대한 폭넓게**
확장한다(목표 160개 이상). 사용자가 "데이터를 많이 넣고 싶다"고 명시했으므로, 처음 스펙의
상한(120)을 넘겨도 된다. 단, 양을 늘리되 검색 품질(목적어로 정확히 찾힘)과 무결성(중복·깨진
참조 없음)을 유지하는 것이 조건이다.

## 2. 작업 규약 (반드시 준수)

이 문서를 받은 에이전트는 아래 규약을 모든 단계에서 지킨다. 규약 위반은 구현 실패로 간주한다.

### 1. 검증 없이 다음 단계로 넘어가지 않는다
- 데이터 추가 후 **기존 자동 테스트를 실제로 돌려** 통과를 확인한다(특히 id 유일성, related
  참조 무결성, category 검증).
- 추가 항목이 실제로 검색되는지 표본으로 확인한다(동의어 입력 → 해당 항목 상위 노출).
- 추론한 사항은 "가설"로 명시하고 검증 후 확정한다. (예: 단축키 키 조합이 실제 엑셀과 같은지
  확신이 없으면 추정으로 표시하고, 확인 가능한 출처로 검증하거나 사용자에게 확인 요청.)

### 2. 근본 원인을 해결한다 (임시방편 금지)
- 테스트 실패 시(중복 id, 깨진 related, 잘못된 category) 테스트를 느슨하게 바꾸지 말고
  데이터를 고친다.

### 3. 진행상황을 보고한다
- 카테고리·subcategory별 최종 분포와 총 개수를 보고한다.
- 넣을지 뺄지 판단한 항목(예: 거의 안 쓰이는 함수)은 이유와 함께 알린다.
- 단축키 키 조합처럼 사실 검증이 필요한 부분에서 불확실한 게 있으면 추측하지 말고 보고한다.

### 4. 검증·테스트를 산출물에 포함한다
- 확장 후 전체 테스트 통과 결과와 신규 주제 검색 표본을 근거로 제시한다.

## 3. 저작권 방침 (반드시 준수)

첨부 자료(네이버 블로그 pisibook의 함수 목록, 단축키 모음, 오빠두 워크북)는 타인의 콘텐츠다.
**함수명·기능 분류·단축키 조합 같은 사실 정보는 참고하되, 모든 설명 텍스트(purpose, note,
purpose_tags, example)는 직접 작성한다.** 첨부 자료의 설명 문구("~를 반환" 등)를 그대로
복사하지 않는다. 예시 수식도 중립적인 일반 예시로 직접 만든다.

## 4. 상세 명세

### 4.1 스키마 (변경 없음) + category/subcategory 규칙 (중요)

`search.py`가 검증하는 현재 스키마를 그대로 따른다. 필드 추가 없음.

- **`category`는 반드시 5개 중 하나**: `함수`, `데이터 도구`, `피벗`, `조건부 서식`, `단축키`.
  이 5개가 UI 칩과 1:1로 묶여 있고 search.py가 이 값만 허용한다. **다른 값을 넣으면 스키마
  검증에서 거부된다.**
- **정보 함수·데이터베이스 함수·수학 함수는 모두 `category: "함수"`로 두고, `subcategory`로만
  구분한다.** category에 "정보 함수" 같은 값을 넣지 않는다(검증 실패 원인).
- 함수 `subcategory` 허용 값(자유롭게 추가 가능, 일관되게 사용): `찾기/참조`, `텍스트`, `날짜`,
  `집계`, `논리`, `동적배열`, `수학`, `정보`, `데이터베이스`, `통계`. 새 subcategory 추가는
  허용된다(사용자 승인). 다만 표기를 통일한다(같은 분류를 다른 이름으로 쓰지 않기).
- `id` 영소문자 스네이크, 전체 유일. `related`는 존재하는 id만.

### 4.2 기존 102개 처리
- **기존 102개는 유지한다(회귀 금지 대상).** 내용을 함부로 바꾸지 않는다.
- 신규 항목이 기존과 **중복되지 않게** 한다(같은 기능을 id만 달리해 재등록 금지).
- 기존 항목과 관계가 있으면 `related`로 양방향 연결(예: 신규 MATCH ↔ 기존 index_match).
- **sc_borders 관련 주의**: 현재 데이터의 테두리 단축키는 정확하다 —
  `Alt → H → B → A`(모든 테두리, 내부 선 포함)와 `Ctrl+Shift+7`/`&`(바깥 테두리만)은 서로
  다른 기능이다. 이를 동일하게 합치거나 "수정"하지 않는다.

### 4.3 추가할 항목 (첨부 목록 기반, 최대한 포함)

아래는 첨부 함수 목록·단축키 모음에서 현재 데이터에 없는 항목이다. **중복 점검 후 최대한
추가**한다. (이미 있는 것은 제외 — 괄호로 표시)

**함수 — 논리/정보**
- NOT, (AND/OR 있음), (IF/IFS/IFERROR/IFNA 있음)
- 정보 함수(subcategory "정보"): ISBLANK, ISNUMBER, ISTEXT, ISERROR, ISNA, NA

**함수 — 통계/집계** (subcategory "집계" 또는 "통계")
- COUNTBLANK, MODE(MODE.SNGL/MODE.MULT), MAXA/MINA, RANK.AVG, AGGREGATE
- (SUM/AVERAGE/COUNT/COUNTA/MAX/MIN/MAXIFS/MINIFS/LARGE/SMALL/RANK/SUMIF/SUMIFS/
  COUNTIF/AVERAGEIF/SUBTOTAL/SUMPRODUCT 있음)

**함수 — 찾기/참조**
- MATCH(단독 — 기존 index_match 묶음과 별개로 "위치 찾기" 검색 대응), COLUMN/COLUMNS,
  ROWS(기존 row_column과 관계), TRANSPOSE(행↔열 전환), GETPIVOTDATA, HYPERLINK
- (XLOOKUP/VLOOKUP/HLOOKUP/INDEX+MATCH/OFFSET/LOOKUP/CHOOSE/INDIRECT/XMATCH/ROW 있음)

**함수 — 수학** (subcategory "수학")
- ABS, CEILING(/.MATH), FLOOR(/.MATH), MROUND, RAND, RANDBETWEEN
- (ROUND/ROUNDUP/ROUNDDOWN/INT/MOD 있음 — 기존은 "집계"였으나 신규 수학 항목과
  subcategory 표기를 통일할지 판단해 보고. 기존 값을 바꾸는 경우 회귀 주의.)

**함수 — 날짜**
- TIME, WEEKNUM, YEARFRAC
- (TODAY/NOW/DATE/YEAR/MONTH/DAY/HOUR/MINUTE/SECOND/DATEDIF/EDATE/EOMONTH/
  WEEKDAY/NETWORKDAYS/WORKDAY 있음)

**함수 — 데이터베이스** (subcategory "데이터베이스")
- DSUM, DGET, DAVERAGE, DCOUNT, DCOUNTA, DMAX, DMIN, DPRODUCT
- note에 "조건 범위를 따로 두는 옛 방식. 요즘은 SUMIFS/FILTER가 더 간편" 취지를 직접 표현해
  맥락을 준다.

**단축키 — 추가**
- 실행취소/재실행(Ctrl+Z / Ctrl+Y), 행·열 삽입(Ctrl + +)/삭제(Ctrl + -),
  행 숨기기/해제(Ctrl+9 / Ctrl+Shift+9), 열 숨기기/해제(Ctrl+0 / Ctrl+Shift+0),
  워크시트 처음/끝(Ctrl+Home / Ctrl+End), 시트 이동(Ctrl+PageUp / Ctrl+PageDown),
  선택 범위 일괄 입력(Ctrl+Enter), 수식 보기(Ctrl+~),
  글꼴 굵게/기울임/밑줄(Ctrl+B / Ctrl+I / Ctrl+U),
  서식 단축키(통화 Ctrl+Shift+4, 숫자 Ctrl+Shift+1 — 기존 천단위와 관계 연결),
  셀 병합(Alt → H → M → M — **note에 "병합은 정렬·필터·복사를 방해하니 가급적 '선택 영역의
  가운데로'(center_across) 권장" 주의 포함**).
- (저장/선택하여 붙여넣기/아래로 채우기/현재 영역 선택/날짜 입력/찾기·바꾸기/테두리/자동합계/
  셀서식/줄바꿈/절대참조/셀편집 있음)

### 4.4 품질 기준 (양이 늘수록 더 중요)
- **동의어 태그**: 항목마다 "이름 모르는 사용자가 칠 말"을 최소 4~6개. 한영 표기(영문명 +
  한글 음차), 구어체, 흔한 오타 포함. 항목이 많아질수록 이게 검색 적중을 좌우한다.
- **중복 회피**: 의미가 거의 같은 기존 항목이 있으면 새로 만들지 말고 기존 항목의 태그를
  보강하는 방향으로(이 경우 기존 항목 수정은 태그 추가에 한하며 보고).
- **related 무결성**: 신규 항목 간, 신규↔기존 간 연결 시 존재하는 id만 참조.
- M365/특정 버전 전용 함수는 note에 버전과 구버전 대체법 명시.

## 5. 파일 구조
- 변경 파일: `data/excel_functions.json` 한 개. **코드 파일은 건드리지 않는다.**
- 스키마 한계로 코드 변경이 필요하다고 판단되면 진행 전에 보고하고 합의한다.

## 6. 검증 계획 (필수)
- 기존 자동 테스트 전부 통과(로드, 5개 category 존재, id 유일성, related 무결성, category
  검증, 검색 동작).
- **category 검증 집중**: 새로 추가한 정보/DB/수학 함수가 모두 category="함수"이고
  subcategory로만 구분됐는지 확인(category에 잘못된 값이 들어가면 즉시 실패).
- 신규 주제 검색 표본: "절댓값"→ABS, "난수"→RAND, "최빈값"→MODE, "행열 바꾸기"→TRANSPOSE,
  "실행취소"→Ctrl+Z, "몇째 주"→WEEKNUM, "빈 셀 개수"→COUNTBLANK, "위치 찾기"→MATCH,
  "DB 합계"→DSUM 등 의도한 항목이 상위 노출되는지.
- 앱 기동 스모크: 전체 항목 로드·렌더, 카테고리 칩 필터 정상, rc=0.
- 최종 총 개수와 category·subcategory별 분포 보고.

## 7. 구현 우선순위
1. 첨부 목록에서 누락 함수 추가(찾기참조·집계·수학·날짜·논리·정보·DB 순) — category/subcategory
   규칙 지키며.
2. 누락 단축키 추가(빈출 위주, 병합은 주의 문구 포함).
3. 동의어 태그 품질 점검 + related 연결.
4. 전체 검증.

## 8. 완료의 정의 (Definition of Done)
- 총 항목 수 160개 이상.
- 첨부 함수 목록·단축키 모음의 빈출 항목이 (중복 제외) 최대한 반영됐다.
- 정보/DB/수학 함수가 모두 category="함수" + subcategory 구분으로 들어갔다(category 오용 0).
- 기존 102개 유지, 중복 없음(회귀 없음). sc_borders 등 정확한 기존 항목을 잘못 수정하지 않았다.
- 모든 설명 텍스트가 직접 작성됐다(첨부 문구 복사 없음).
- 전체 테스트 통과 + 신규 주제 검색 표본 확인 결과를 근거로 보고했다.
- 넣고 뺀 판단과 subcategory 표기 결정을 보고했다.
