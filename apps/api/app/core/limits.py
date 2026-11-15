"""Límites de uso en memoria (un proceso). Para varios workers en producción migrar a Redis/DB con la misma interfaz."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager


class RateLimited(Exception):
    def __init__(self, retry_after: int, detail: str):
        super().__init__(detail)
        self.retry_after, self.detail = retry_after, detail


class SlidingWindowLimiter:
    """Máximo `limit` eventos por identidad en `window_s` segundos."""

    def __init__(self, window_s: float = 3600.0, clock=time.monotonic):
        self.window_s, self._clock = window_s, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_add(self, subject: str, limit: int) -> None:
        now = self._clock()
        with self._lock:
            q = self._events[subject]
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if len(q) >= limit:
                retry = int(self.window_s - (now - q[0])) + 1
                raise RateLimited(retry, f"Límite de {limit} extracciones nuevas por hora alcanzado")
            q.append(now)

    def remaining(self, subject: str, limit: int) -> int:
        now = self._clock()
        with self._lock:
            q = self._events[subject]
            return max(0, limit - sum(1 for t in q if now - t < self.window_s))


class ExtractionGate:
    """Limita extracciones simultáneas contra Earth Engine (cuotas de concurrencia del proyecto)."""

    def __init__(self, max_concurrent: int, wait_s: float = 10.0):
        self._sem = threading.BoundedSemaphore(max_concurrent)
        self.wait_s = wait_s

    @contextmanager
    def slot(self):
        if not self._sem.acquire(timeout=self.wait_s):
            raise RateLimited(30, "Earth Engine está ocupado con otras extracciones; reintenta en unos segundos")
        try:
            yield
        finally:
            self._sem.release()
