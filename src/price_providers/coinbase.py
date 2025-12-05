from typing import Dict, List, Tuple
import requests

from src.price_providers.base import PriceProvider
from src.logger_utils import get_logger


class CoinbaseProvider(PriceProvider):
    name = "coinbase"

    def __init__(self, base_url: str = "https://api.coinbase.com/v2", rpm: int = 60, timeout: int = 8):
        super().__init__(rpm=rpm)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def batch_fetch(self, pairs: List[str], quote: str) -> Tuple[Dict[str, float], Exception]:
        logger = get_logger(__name__)
        # pairs expected as COIN-USD, but service maps token->pair
        if not pairs:
            return {}, None
        out: Dict[str, float] = {}
        for pair in pairs:
            if not self.rate_limiter.allow(1.0):
                break
            url = f"{self.base_url}/prices/{pair.upper()}/spot"
            try:
                resp = requests.get(url, timeout=self.timeout)
                logger.debug(f"coinbase GET {resp.url} status={resp.status_code}")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                logger.debug(f"coinbase body={data}")
                amount = (((data or {}).get("data") or {}).get("amount"))
                if amount is not None:
                    try:
                        out[pair.upper()] = float(amount)
                    except Exception:
                        pass
            except Exception:
                continue
        return out, None


