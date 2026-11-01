"""Keeps freshly made MP3 files for a few minutes.

The MP3 pages let people listen to a preview first and then download. Both requests ask for the same file, so the
first one makes it and the second one reuses it instead of converting again. Files are deleted after `ttl` seconds.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time


class AudioCache:
    def __init__(self, ttl: int = 600, max_items: int = 24):
        self.ttl, self.max_items = ttl, max_items
        self._items: dict[str, tuple[float, str]] = {}      # key -> (expires at, file path)
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _drop(self, key: str) -> None:
        item = self._items.pop(key, None)
        if item:
            shutil.rmtree(os.path.dirname(item[1]), ignore_errors=True)
        self._locks.pop(key, None)

    def _sweep(self) -> None:
        now = time.time()
        for key in [k for k, (exp, path) in self._items.items() if exp < now or not os.path.exists(path)]:
            self._drop(key)
        while len(self._items) > self.max_items:
            self._drop(min(self._items, key=lambda k: self._items[k][0]))

    def get(self, key: str, make) -> str:
        """Return the path of the file for `key`. `make(folder)` creates it (inside `folder`) when it isn't cached yet."""
        with self._guard:
            self._sweep()
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:                                           # two requests for the same file wait for one conversion
            with self._guard:
                hit = self._items.get(key)
                if hit and os.path.exists(hit[1]):
                    return hit[1]
            folder = tempfile.mkdtemp(prefix="audio_")
            try:
                path = make(folder)
            except BaseException:
                shutil.rmtree(folder, ignore_errors=True)
                raise
            with self._guard:
                self._items[key] = (time.time() + self.ttl, path)
                self._sweep()
            return path
