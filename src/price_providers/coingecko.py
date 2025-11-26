import os
from typing import Dict, List, Tuple
import requests

from src.price_providers.base import PriceProvider
from src.logger_utils import get_logger


class CoinGeckoProvider(PriceProvider):
    name = "coingecko"

    def __init__(self, base_url: str, rpm: int = 50, timeout: int = 10):
        super().__init__(rpm=rpm)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def batch_fetch(self, ids: List[str], quote: str) -> Tuple[Dict[str, float], Exception]:
        logger = get_logger(__name__)
        if not ids:
            return {}, None
        if not self.rate_limiter.allow(1.0):
            return {}, Exception("rate_limited")

        params = {
            "ids": ",".join(ids),
            "vs_currencies": quote,
        }
        try:
            resp = requests.get(self.base_url, params=params, timeout=self.timeout)
            logger.debug(f"coingecko GET {resp.url} status={resp.status_code}")
            if resp.status_code != 200:
                return {}, Exception(f"coingecko http {resp.status_code}")
            data = resp.json()
            logger.debug(f"coingecko body={data}")
            out: Dict[str, float] = {}
            for asset_id, m in data.items():
                if isinstance(m, dict) and quote in m and m[quote] is not None:
                    try:
                        out[asset_id] = float(m[quote])
                    except Exception:
                        continue
            return out, None
        except Exception as e:
            return {}, Exception(f"coingecko error: {e}")


