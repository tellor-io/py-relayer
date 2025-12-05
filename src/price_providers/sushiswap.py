from typing import Dict, List, Tuple
import requests

from src.price_providers.base import PriceProvider
from src.logger_utils import get_logger


class SushiKatanaProvider(PriceProvider):
    name = "sushiswap"

    def __init__(self, base_url: str = "https://api.sushi.com/price/v1/747474", rpm: int = 60, timeout: int = 8):
        super().__init__(rpm=rpm)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def batch_fetch(self, addresses: List[str], quote: str) -> Tuple[Dict[str, float], Exception]:
        logger = get_logger(__name__)
        # quote ignored; API returns USD
        if not addresses:
            return {}, None
        out: Dict[str, float] = {}
        for addr in addresses:
            if not self.rate_limiter.allow(1.0):
                break
            url = f"{self.base_url}/{addr}"
            try:
                resp = requests.get(url, timeout=self.timeout)
                logger.debug(f"sushiswap GET {resp.url} status={resp.status_code}")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                logger.debug(f"sushiswap body={data}")
                # observed formats: number directly, or object with 'price' or at key address
                price = None
                if isinstance(data, (int, float)):
                    price = float(data)
                elif isinstance(data, dict):
                    if "price" in data and data["price"] is not None:
                        price = float(data["price"])
                    elif addr.lower() in data and data[addr.lower()] is not None:
                        try:
                            price = float(data[addr.lower()])
                        except Exception:
                            price = None
                if price is not None and price > 0:
                    out[addr.lower()] = price
            except Exception:
                continue
        return out, None


