from typing import Dict, List, Tuple
import requests

from src.price_providers.base import PriceProvider
from src.logger_utils import get_logger


class CoinPaprikaProvider(PriceProvider):
    name = "coinpaprika"

    def __init__(self, base_url: str = "https://api.coinpaprika.com/v1", rpm: int = 30, timeout: int = 10):
        super().__init__(rpm=rpm)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def batch_fetch(self, ids: List[str], quote: str) -> Tuple[Dict[str, float], Exception]:
        logger = get_logger(__name__)
        if not ids:
            return {}, None
        out: Dict[str, float] = {}
        # CoinPaprika has no multi-id batch; loop but respect rate limit
        for coin_id in ids:
            if not self.rate_limiter.allow(1.0):
                # if limited, skip remaining (callers can combine with other providers)
                break
            url = f"{self.base_url}/tickers/{coin_id}"
            params = {"quotes": quote.upper()}
            try:
                resp = requests.get(url, params=params, timeout=self.timeout)
                logger.debug(f"coinpaprika GET {resp.url} status={resp.status_code}")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                logger.debug(f"coinpaprika body={data}")
                price = (((data or {}).get("quotes") or {}).get(quote.upper()) or {}).get("price")
                if price is not None:
                    try:
                        out[coin_id] = float(price)
                    except Exception:
                        pass
            except Exception:
                continue
        return out, None


