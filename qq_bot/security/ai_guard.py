from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager
import re
import time
from typing import AsyncIterator, Hashable


class AiInputRejected(ValueError):
    pass


class AiOutputRejected(ValueError):
    pass


class AiBusy(RuntimeError):
    pass


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENSITIVE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|authorization)\s*[:=]\s*\S{12,}"),
)


def _contains_sensitive_value(
    text: str,
    *,
    forbidden_values: Iterable[str] = (),
) -> bool:
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS) or any(
        value and value in text for value in forbidden_values
    )


def normalize_user_input(
    raw: str,
    *,
    max_chars: int,
    forbidden_values: Iterable[str] = (),
) -> str:
    text = _CONTROL_CHARACTERS.sub("", raw).strip()
    if not text:
        raise AiInputRejected("empty input")
    if len(text) > max_chars:
        raise AiInputRejected("input too long")
    if _contains_sensitive_value(text, forbidden_values=forbidden_values):
        raise AiInputRejected("input appears to contain a secret")
    return text


def sanitize_model_output(
    raw: str,
    *,
    max_chars: int,
    forbidden_values: Iterable[str] = (),
) -> str:
    text = _CONTROL_CHARACTERS.sub("", raw).strip()
    if not text:
        raise AiOutputRejected("empty output")
    if _contains_sensitive_value(text, forbidden_values=forbidden_values):
        raise AiOutputRejected("output appears to contain a secret")
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


class SlidingWindowRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: float,
        max_keys: int = 4096,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._requests: OrderedDict[Hashable, deque[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def allow(self, key: Hashable) -> bool:
        now = self._clock()
        cutoff = now - self._window_seconds
        async with self._lock:
            history = self._requests.setdefault(key, deque())
            while history and history[0] <= cutoff:
                history.popleft()

            allowed = len(history) < self._max_requests
            if allowed:
                history.append(now)
            self._requests.move_to_end(key)
            while len(self._requests) > self._max_keys:
                self._requests.popitem(last=False)
            return allowed


class AiConcurrencyLimiter:
    def __init__(self, max_concurrency: int) -> None:
        self._max_concurrency = max_concurrency
        self._active = 0
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        async with self._lock:
            if self._active >= self._max_concurrency:
                raise AiBusy("AI request concurrency limit reached")
            self._active += 1

        try:
            yield
        finally:
            async with self._lock:
                self._active -= 1