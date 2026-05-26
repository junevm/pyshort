"""Lightweight in-memory sliding-window rate limiter.

Good enough for single-process deployments and tests. For multi-worker
production you'd swap the backend for Django's cache (Redis/Memcached);
the public ``allow()`` API is intentionally cache-compatible.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

_lock = threading.Lock()
_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def allow(key: str, limit: int, window_seconds: int) -> bool:
    """Return True if ``key`` is still under ``limit`` hits in ``window_seconds``."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def reset(key: str | None = None) -> None:
    """Clear one key (or everything). Used by tests."""
    with _lock:
        if key is None:
            _buckets.clear()
        else:
            _buckets.pop(key, None)
