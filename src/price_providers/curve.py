from typing import Dict, List, Tuple
import requests

from src.price_providers.base import PriceProvider


class CurvePriceApiProvider(PriceProvider):
    name = "curve"

    def __init__(self, base_url: str = "https://prices.curve.fi/v1/usd_price/ethereum", rpm: int = 60, timeout: int = 8):
        super().__init__(rpm=rpm)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def batch_fetch(self, addresses: List[str], quote: str) -> Tuple[Dict[str, float], Exception]:
        # Curve API is per-address; no batch endpoint
        if not addresses:
            return {}, None
        out: Dict[str, float] = {}
        for addr in addresses:
            if not self.rate_limiter.allow(1.0):
                break
            url = f"{self.base_url}/{addr}"
            try:
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                price = ((data or {}).get("data") or {}).get("usd_price")
                if price is not None:
                    try:
                        out[addr.lower()] = float(price)
                    except Exception:
                        pass
            except Exception:
                continue
        return out, None


