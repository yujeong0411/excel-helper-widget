"""데이터 파일 변경 감시(watchdog) → Qt 메인 스레드로 시그널 전달.

watchdog 콜백은 별도 스레드에서 돈다. Qt 위젯을 직접 건드리지 않고,
QObject 시그널(QueuedConnection)로 메인 스레드에 변경을 알린다.
디바운스는 수신 측(widget.schedule_reload → QTimer)에서 처리한다.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except Exception:  # pragma: no cover - watchdog 미설치/플랫폼 이슈
    FileSystemEventHandler = object  # type: ignore
    Observer = None  # type: ignore


class ReloadBridge(QObject):
    """watchdog(다른 스레드) → Qt 메인 스레드로 변경 신호 전달."""

    changed = pyqtSignal()


class _Handler(FileSystemEventHandler):
    def __init__(self, target: Path, bridge: ReloadBridge):
        super().__init__()
        self._target = str(target.resolve())
        self._bridge = bridge

    def _matches(self, *raw_paths: str) -> bool:
        for p in raw_paths:
            if not p:
                continue
            try:
                if str(Path(p).resolve()) == self._target:
                    return True
            except OSError:
                if p == self._target:
                    return True
        return False

    def on_modified(self, event):  # noqa: N802
        if not event.is_directory and self._matches(event.src_path):
            self._bridge.changed.emit()

    def on_created(self, event):  # noqa: N802
        if not event.is_directory and self._matches(event.src_path):
            self._bridge.changed.emit()

    def on_moved(self, event):  # noqa: N802
        # 에디터가 임시파일→원본 rename 으로 저장하는 경우(원자적 저장) 대응
        if self._matches(event.src_path, getattr(event, "dest_path", "")):
            self._bridge.changed.emit()


class Reloader:
    """대상 파일이 든 디렉터리를 감시. start()/stop()."""

    def __init__(self, data_path: Path):
        self.bridge = ReloadBridge()
        self._path = Path(data_path)
        self._observer = None

    def available(self) -> bool:
        return Observer is not None

    def start(self) -> bool:
        """감시 시작. 성공 여부 반환(실패해도 앱은 정상, 수동 새로고침으로 폴백)."""
        if Observer is None:
            return False
        try:
            self._observer = Observer()
            handler = _Handler(self._path, self.bridge)
            self._observer.schedule(handler, str(self._path.parent), recursive=False)
            self._observer.daemon = True
            self._observer.start()
            return True
        except Exception:
            self._observer = None
            return False

    def stop(self) -> None:
        obs = self._observer
        self._observer = None
        if obs is not None:
            try:
                obs.stop()
                obs.join(timeout=2)
            except Exception:
                pass
