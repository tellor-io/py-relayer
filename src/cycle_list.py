from __future__ import annotations

import os
import time
from typing import Iterable, Optional, Set

from src.layer_client import get_cycle_list, strip_0x
from src.logger_utils import get_logger

logger = get_logger(__name__)


def _normalize_hex_no_0x(v: str) -> str:
    return strip_0x(str(v)).lower()


class CycleListCache:
    """
    Periodically fetches the Layer oracle cycle list and provides membership checks.
    Best-effort by design: failures keep the last known cache.
    """

    def __init__(self, refresh_seconds: Optional[float] = None):
        self._refresh_seconds = float(
            refresh_seconds if refresh_seconds is not None else os.getenv("CYCLE_LIST_REFRESH_SECONDS", "300")
        )
        self._last_fetch_ts: float = 0.0
        self._cycle_list: Set[str] = set()  # normalized queryData hex (no 0x, lowercase)

    def _update_from_items(self, items: Iterable[str]) -> None:
        self._cycle_list = {_normalize_hex_no_0x(x) for x in items if x is not None}

    def refresh_if_needed(self, *, force: bool = False) -> None:
        now = time.time()
        if not force and self._last_fetch_ts and (now - self._last_fetch_ts) < self._refresh_seconds:
            return

        resp, err = get_cycle_list()
        if err is not None or resp is None:
            logger.warning(f"Failed to refresh cycle list (keeping last cache): {err}")
            self._last_fetch_ts = now
            return

        items = resp.get("cycle_list")
        if not isinstance(items, list):
            logger.warning(f"Unexpected cycle list response shape (keeping last cache): {resp}")
            self._last_fetch_ts = now
            return

        self._update_from_items(items)
        self._last_fetch_ts = now
        logger.debug(f"Cycle list refreshed: {len(self._cycle_list)} items")

    def contains_query_data(self, query_data_hex: str) -> bool:
        self.refresh_if_needed()
        q = _normalize_hex_no_0x(query_data_hex)
        return q in self._cycle_list


