from __future__ import annotations

import random
import time
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


def poll_with_backoff(
    check_fn: Callable[[], Optional[T]],
    *,
    fast_attempts: int = 8,
    fast_sleep: float = 0.5,
    backoff_factor: float = 1.5,
    max_sleep: float = 5.0,
    timeout: float = 30.0,
    jitter_ratio: float = 0.10,
    description: str = "condition",
) -> T:
    """
    Poll `check_fn` until it returns a non-None value, using:
    - a fast polling phase (fast_attempts * fast_sleep)
    - then exponential backoff up to max_sleep
    - until timeout seconds elapse
    """
    if fast_attempts < 0:
        raise ValueError("fast_attempts must be >= 0")
    if fast_sleep <= 0:
        raise ValueError("fast_sleep must be > 0")
    if backoff_factor <= 1:
        raise ValueError("backoff_factor must be > 1")
    if max_sleep <= 0:
        raise ValueError("max_sleep must be > 0")
    if timeout <= 0:
        raise ValueError("timeout must be > 0")
    if jitter_ratio < 0:
        raise ValueError("jitter_ratio must be >= 0")

    start = time.time()

    # fast polling phase
    for attempt in range(fast_attempts):
        out = check_fn()
        if out is not None:
            return out
        if time.time() - start >= timeout:
            raise TimeoutError(f"Timed out waiting for {description} after {timeout:.1f}s")
        time.sleep(fast_sleep)

    # backoff phase
    sleep_s = min(max_sleep, fast_sleep)
    while True:
        out = check_fn()
        if out is not None:
            return out

        elapsed = time.time() - start
        if elapsed >= timeout:
            raise TimeoutError(f"Timed out waiting for {description} after {timeout:.1f}s")

        jitter = random.uniform(0, sleep_s * jitter_ratio) if jitter_ratio else 0.0
        time.sleep(min(max_sleep, sleep_s) + jitter)
        sleep_s = min(max_sleep, sleep_s * backoff_factor)


