"""Small atomic filesystem cache shared by catalog consumers."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from .errors import CatalogError


class CatalogCache:
    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        configured = os.environ.get(
            "BIOMERO_WORKFLOW_SKILLS_CACHE_DIR", ""
        ).strip()
        default = Path.home() / ".cache/biomero-workflow-skills"
        self.root = Path(root or configured or default)

    @contextmanager
    def locked(self, timeout: float = 15.0) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / ".lock"
        deadline = time.monotonic() + timeout
        while True:
            try:
                descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, f"{os.getpid()} {time.time()}".encode("ascii"))
                os.close(descriptor)
                break
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime > timeout * 4:
                        lock.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise CatalogError(
                        "Timed out waiting for the workflow skills cache lock"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            lock.unlink(missing_ok=True)

    def read_json(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def write_json(self, key: str, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle, temporary = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _path(self, key: str) -> Path:
        if not key or any(part in {"", ".", ".."} for part in key.replace("\\", "/").split("/")):
            raise CatalogError("Invalid cache key")
        candidate = (self.root / f"{key}.json").resolve()
        root = self.root.resolve()
        if root not in candidate.parents:
            raise CatalogError("Cache key escapes the catalog cache")
        return candidate
