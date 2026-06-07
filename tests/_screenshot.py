"""위젯 외형을 PNG 로 캡처(시각 확인용). 테스트 비대상."""

import sys

from PyQt6.QtWidgets import QApplication

from app import paths
from app.search import load_items
from app.settings import Settings
from app.widget import ExcelHelperWidget

app = QApplication(sys.argv)
items = load_items(paths.data_file())
w = ExcelHelperWidget(items, Settings(path=paths._external_dir() / "tests" / "_tmp.json"))
w.search_box.setText("XLOOKUP")
w._run_search()
w.resize(360, 600)
w.show()
app.processEvents()
if w.cards:
    w.cards[0].set_expanded(True)  # 함수 카드(예시+복사 버튼) 펼침
for _ in range(5):
    app.processEvents()
out = paths._external_dir() / "tests" / "_preview.png"
w.grab().save(str(out))
print(f"saved {out}")
