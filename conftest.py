"""프로젝트 루트를 import 경로에 추가해 `app` 패키지를 테스트에서 import 가능하게 함."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
