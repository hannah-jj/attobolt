"""Map Slack thread_ts -> Claude CLI session info."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "sessions.json"


def _path() -> Path:
    return Path(os.environ.get("SESSIONS_FILE", str(_DEFAULT_PATH)))


@dataclass
class SessionInfo:
    session_id: str
    cwd: str | None = None


class SessionStore:
    """File-backed mapping of Slack thread timestamps to Claude session info."""

    def __init__(self) -> None:
        self._store: dict[str, SessionInfo] = self._load()

    def get(self, thread_ts: str) -> SessionInfo | None:
        return self._store.get(thread_ts)

    def set(self, thread_ts: str, session_id: str, cwd: str | None = None) -> None:
        self._store[thread_ts] = SessionInfo(session_id=session_id, cwd=cwd)
        self._save()

    def _load(self) -> dict[str, SessionInfo]:
        p = _path()
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text())
            return {
                ts: SessionInfo(session_id=v["session_id"], cwd=v.get("cwd"))
                for ts, v in data.items()
            }
        except (json.JSONDecodeError, KeyError):
            return {}

    def _save(self) -> None:
        p = _path()
        data = {
            ts: {"session_id": info.session_id, "cwd": info.cwd}
            for ts, info in self._store.items()
        }
        p.write_text(json.dumps(data, indent=2))
