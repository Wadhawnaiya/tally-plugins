from __future__ import annotations

import json
import os
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_STATE_PATH = Path.home() / ".tallymind" / "state.json"


@contextmanager
def _file_lock(handle) -> Iterator[None]:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TallyMindState:
    host: str = "localhost"
    port: int = 9000
    company: str | None = None
    pending_previews: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TallyMindState":
        return cls(
            host=data.get("host", "localhost"),
            port=int(data.get("port", 9000)),
            company=data.get("company"),
            pending_previews=dict(data.get("pending_previews", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "company": self.company,
            "pending_previews": self.pending_previews,
        }

    def add_preview(self, kind: str, description: str, xml: str, company: str | None) -> str:
        preview_id = secrets.token_hex(4)
        self.pending_previews[preview_id] = {
            "kind": kind,
            "description": description,
            "xml": xml,
            "company": company,
            "created_at": _now_iso(),
        }
        return preview_id

    def pop_preview(self, preview_id: str) -> dict[str, Any]:
        return self.pending_previews.pop(preview_id)


class TallyMindStateStore:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path).expanduser() if path else DEFAULT_STATE_PATH

    def load(self) -> TallyMindState:
        if not self.path.exists():
            return TallyMindState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return TallyMindState()
        return TallyMindState.from_dict(data)

    def save(self, state: TallyMindState) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            with _file_lock(handle):
                handle.seek(0)
                handle.truncate()
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        return self.path
