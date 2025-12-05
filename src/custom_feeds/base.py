from typing import Callable, Dict, Any


class CustomFeedHandler:
    """
    Base interface for custom price feed handlers.

    Implementations should compute a price for the target feed using any
    combination of external providers, on-chain data via EVM RPC calls,
    and/or other configured feeds provided by the standard aggregator.

    Expected return: dict with keys {"price": float, "sources": dict, "ts": int}
    and raise an Exception on error.
    """

    def fetch(
        self,
        feed_cfg: Dict[str, Any],
        fetch_for_feeds: Callable[[list[str]], Dict[str, Dict[str, float]]],
        agg_fn: Callable[[list[float]], float],
        evm_resolver: Any,
    ) -> Dict[str, Any]:
        raise NotImplementedError


