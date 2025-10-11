from typing import Dict, Tuple, List
import os
import requests


class PriceServiceClient:
    def __init__(self, base_url: str, timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_price(self, feed: str, agg: str = "median", required: int = 1) -> Tuple[float, Exception]:
        try:
            resp = requests.get(f"{self.base_url}/price", params={"feed": feed, "agg": agg, "required": str(required)}, timeout=self.timeout)
            if resp.status_code != 200:
                return None, Exception(f"price-service http {resp.status_code}: {resp.text}")
            data = resp.json()
            return float(data.get("price")), None
        except Exception as e:
            return None, Exception(f"price-service error: {e}")

    def get_batch(self, feeds: List[str], agg: str = "median", required: int = 1) -> Tuple[Dict[str, float], Exception]:
        try:
            resp = requests.get(
                f"{self.base_url}/batch",
                params={"feeds": ",".join(feeds), "agg": agg, "required": str(required)},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return {}, Exception(f"price-service http {resp.status_code}: {resp.text}")
            data = resp.json()
            out: Dict[str, float] = {}
            for k, v in data.items():
                if isinstance(v, dict) and "price" in v and v["price"] is not None:
                    try:
                        out[k] = float(v["price"])
                    except Exception:
                        continue
            return out, None
        except Exception as e:
            return {}, Exception(f"price-service error: {e}")


def get_price_from_service() -> Tuple[float, Exception]:
    base = os.getenv("PRICE_SERVICE_URL")
    feed = os.getenv("FEED_NAME")
    if not base or not feed:
        return None, Exception("price-service not configured")
    agg = os.getenv("PRICE_AGGREGATION", "median")
    try:
        required = int(os.getenv("REQUIRED_SOURCES", "1"))
    except Exception:
        required = 1
    client = PriceServiceClient(base)
    return client.get_price(feed, agg=agg, required=required)


