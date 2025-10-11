from typing import Dict, List, Tuple
import requests

from src.price_providers.base import PriceProvider


class CoinMarketCapProvider(PriceProvider):
    name = "coinmarketcap"

    def __init__(self, base_url: str, api_key: str, rpm: int = 30, timeout: int = 10):
        super().__init__(rpm=rpm)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def batch_fetch(self, symbols: List[str], quote: str) -> Tuple[Dict[str, float], Exception]:
        if not symbols:
            return {}, None
        if not self.rate_limiter.allow(1.0):
            return {}, Exception("rate_limited")

        headers = {"X-CMC_PRO_API_KEY": self.api_key}
        params = {
            "symbol": ",".join(symbols),
            "convert": quote.upper(),
        }
        try:
            resp = requests.get(self.base_url, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                return {}, Exception(f"cmc http {resp.status_code}")
            data = resp.json()
            out: Dict[str, float] = {}
            result_map = data.get("data") or {}
            for sym, entries in result_map.items():
                if isinstance(entries, list) and entries:
                    q = entries[0].get("quote", {})
                    price = (q.get(quote.upper()) or {}).get("price")
                    if price is not None:
                        try:
                            out[sym.upper()] = float(price)
                        except Exception:
                            continue
            return out, None
        except Exception as e:
            return {}, Exception(f"cmc error: {e}")


