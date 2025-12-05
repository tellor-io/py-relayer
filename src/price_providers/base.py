import time
from typing import Dict, List, Tuple


class RateLimiter:
    """
    Simple token bucket rate limiter for per-provider request budgets.
    Tokens represent requests allowed in the current minute window.
    """

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = max(0, int(requests_per_minute or 0))
        self.tokens = float(self.requests_per_minute)
        self.last_refill_ts = time.time()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.time()
        # Refill tokens based on elapsed time (per-minute rate)
        if self.requests_per_minute > 0:
            elapsed = now - self.last_refill_ts
            refill = (elapsed / 60.0) * self.requests_per_minute
            if refill > 0:
                self.tokens = min(self.requests_per_minute, self.tokens + refill)
                self.last_refill_ts = now
        # If rpm is 0, disallow
        if self.requests_per_minute == 0:
            return False
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


class PriceProvider:
    """
    Abstract batch-capable price provider interface.
    Implementations should support fetching multiple assets in a single HTTP request when possible.
    """

    name: str = "base"

    def __init__(self, rpm: int = 60):
        self.rate_limiter = RateLimiter(rpm)

    def batch_fetch(self, ids: List[str], quote: str) -> Tuple[Dict[str, float], Exception]:
        """
        Fetch prices for multiple assets.

        Args:
            ids: Provider-specific asset identifiers (e.g., CoinGecko ids)
            quote: Quote currency (e.g., "usd")

        Returns:
            (mapping id->price, error)
        """
        raise NotImplementedError


