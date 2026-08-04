from __future__ import annotations

import threading

import pytest
from omero_workflow_skills.cache import CatalogCache

from omero_workflow_skills import CatalogError


def test_atomic_roundtrip_and_corruption_recovery(tmp_path):
    cache = CatalogCache(tmp_path)
    with cache.locked():
        cache.write_json("workflows/abc", {"ready": True})
    assert cache.read_json("workflows/abc") == {"ready": True}
    (tmp_path / "workflows" / "abc.json").write_text("{broken", encoding="utf-8")
    assert cache.read_json("workflows/abc") is None


def test_rejects_traversal_key(tmp_path):
    cache = CatalogCache(tmp_path)
    with pytest.raises(CatalogError):
        cache.read_json("../escape")


def test_lock_serializes_writers(tmp_path):
    cache = CatalogCache(tmp_path)
    order: list[int] = []

    def writer(value: int) -> None:
        with cache.locked():
            order.append(value)
            cache.write_json("state", {"writer": value})

    threads = [threading.Thread(target=writer, args=(value,)) for value in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(order) == [0, 1, 2, 3]
    assert cache.read_json("state")["writer"] in range(4)
