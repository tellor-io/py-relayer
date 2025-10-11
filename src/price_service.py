import os
import threading
import time
from typing import Dict, List, Tuple

from flask import Flask, jsonify, request

from src.config_loader import load_config, apply_env
from src.price_providers.coingecko import CoinGeckoProvider
from src.price_providers.coinmarketcap import CoinMarketCapProvider
from src.price_providers.coinpaprika import CoinPaprikaProvider
from src.price_providers.coinbase import CoinbaseProvider
from src.price_providers.curve import CurvePriceApiProvider
from src.price_aggregation import median, trimmed_mean


class CacheEntry:
    def __init__(self, value: float, ts: float):
        self.value = value
        self.ts = ts


class InMemoryCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self._store: Dict[Tuple[str, str, str], CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, provider: str, asset: str, quote: str) -> Tuple[float, bool]:
        key = (provider, asset, quote)
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry and now - entry.ts <= self.ttl:
                return entry.value, True
        return 0.0, False

    def set(self, provider: str, asset: str, quote: str, value: float) -> None:
        key = (provider, asset, quote)
        with self._lock:
            self._store[key] = CacheEntry(value, time.time())


def parse_aggregation(spec: str):
    if not spec or spec == "median":
        return lambda xs: median(xs)
    if spec.startswith("trimmed_mean"):
        try:
            parts = spec.split(":", 1)
            t = float(parts[1]) if len(parts) > 1 else 0.1
        except Exception:
            t = 0.1
        return lambda xs: trimmed_mean(xs, trim=t)
    return lambda xs: median(xs)


def build_app(service_cfg: Dict) -> Flask:
    server_cfg = service_cfg.get("server", {})
    cache_ttl = int(server_cfg.get("cache_ttl_secs", 10))
    cache = InMemoryCache(ttl_seconds=cache_ttl)

    providers_cfg = service_cfg.get("providers", {})
    providers = {}
    # CoinGecko
    cg_cfg = providers_cfg.get("coingecko", {})
    if cg_cfg.get("enabled", True):
        providers["coingecko"] = CoinGeckoProvider(
            base_url=cg_cfg.get("base_url", "https://api.coingecko.com/api/v3/simple/price"),
            rpm=int(cg_cfg.get("rpm", 50)),
        )
    # CoinMarketCap
    cmc_cfg = providers_cfg.get("coinmarketcap", {})
    if cmc_cfg.get("enabled", False) and cmc_cfg.get("api_key"):
        providers["coinmarketcap"] = CoinMarketCapProvider(
            base_url=cmc_cfg.get("base_url", "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"),
            api_key=os.path.expandvars(cmc_cfg.get("api_key")),
            rpm=int(cmc_cfg.get("rpm", 30)),
        )
    # CoinPaprika
    paprika_cfg = providers_cfg.get("coinpaprika", {})
    if paprika_cfg.get("enabled", False):
        providers["coinpaprika"] = CoinPaprikaProvider(
            base_url=paprika_cfg.get("base_url", "https://api.coinpaprika.com/v1"),
            rpm=int(paprika_cfg.get("rpm", 30)),
        )
    # Coinbase spot
    coinbase_cfg = providers_cfg.get("coinbase", {})
    if coinbase_cfg.get("enabled", False):
        providers["coinbase"] = CoinbaseProvider(
            base_url=coinbase_cfg.get("base_url", "https://api.coinbase.com/v2"),
            rpm=int(coinbase_cfg.get("rpm", 60)),
        )
    # Curve price API (per address)
    curve_cfg = providers_cfg.get("curve", {})
    if curve_cfg.get("enabled", False):
        providers["curve"] = CurvePriceApiProvider(
            base_url=curve_cfg.get("base_url", "https://prices.curve.fi/v1/usd_price/ethereum"),
            rpm=int(curve_cfg.get("rpm", 60)),
        )

    feeds_cfg = service_cfg.get("feeds", [])
    feed_map: Dict[str, Dict[str, str]] = {}
    for f in feeds_cfg:
        name = f.get("name")
        if not name:
            continue
        feed_map[name] = f

    app = Flask(__name__)

    def resolve_provider_keys(feed: str) -> Tuple[str, Dict[str, str]]:
        f = feed_map.get(feed, {})
        quote = f.get("quote", "usd").lower()
        keys = {}
        if "coingecko" in providers and f.get("coingecko_id"):
            keys["coingecko"] = f["coingecko_id"].lower()
        if "coinmarketcap" in providers and f.get("coinmarketcap_symbol"):
            keys["coinmarketcap"] = f["coinmarketcap_symbol"].upper()
        if "coinpaprika" in providers and f.get("coinpaprika_id"):
            keys["coinpaprika"] = f["coinpaprika_id"].lower()
        if "coinbase" in providers and f.get("coinbase_pair"):
            keys["coinbase"] = f["coinbase_pair"].upper()  # e.g., ETH-USD
        if "curve" in providers and f.get("curve_address"):
            keys["curve"] = f["curve_address"].lower()
        return quote, keys

    def fetch_for_feeds(feeds: List[str]) -> Dict[str, Dict]:
        # group per provider
        per_provider_ids: Dict[str, Dict[str, List[str]]] = {}
        quotes: Dict[str, str] = {}
        for feed in feeds:
            quote, keys = resolve_provider_keys(feed)
            quotes[feed] = quote
            for prov, key in keys.items():
                per_provider_ids.setdefault(prov, {}).setdefault(quote, []).append(key)

        results: Dict[str, Dict[str, float]] = {feed: {} for feed in feeds}

        # fetch using cache and batch
        for prov, quote_to_ids in per_provider_ids.items():
            provider = providers.get(prov)
            if not provider:
                continue
            for quote, ids in quote_to_ids.items():
                # First, satisfy from cache
                missing: List[str] = []
                cached_values: Dict[str, float] = {}
                for asset in ids:
                    v, hit = cache.get(prov, asset, quote)
                    if hit:
                        cached_values[asset] = v
                    else:
                        missing.append(asset)
                # Batch fetch remaining
                fetched: Dict[str, float] = {}
                if missing:
                    data, err = provider.batch_fetch(missing, quote)
                    if not err and data:
                        fetched = data
                        for asset, price in data.items():
                            cache.set(prov, asset, quote, price)
                # Merge
                merged = {**cached_values, **fetched}
                # Assign back per feed
                for feed in feeds:
                    if quotes.get(feed) != quote:
                        continue
                    _, keys = resolve_provider_keys(feed)
                    key = keys.get(prov)
                    if key and key in merged:
                        results[feed][prov] = merged[key]

        return results

    @app.get("/price")
    def get_price():
        feed = request.args.get("feed")
        if not feed:
            return jsonify({"error": "missing feed"}), 400
        agg_spec = request.args.get("agg", "median")
        required = int(request.args.get("required", "1"))
        agg_fn = parse_aggregation(agg_spec)

        data = fetch_for_feeds([feed]).get(feed, {})
        values = list(data.values())
        if len(values) < max(1, required):
            return jsonify({"error": "insufficient sources", "sources": data}), 424
        try:
            price = float(agg_fn(values))
        except Exception:
            return jsonify({"error": "aggregation failed", "sources": data}), 422
        return jsonify({"feed": feed, "price": price, "sources": data, "ts": int(time.time())})

    @app.get("/batch")
    def get_batch():
        feeds_raw = request.args.get("feeds", "").strip()
        if not feeds_raw:
            return jsonify({"error": "missing feeds"}), 400
        feeds = [f for f in feeds_raw.split(",") if f]
        agg_spec = request.args.get("agg", "median")
        required = int(request.args.get("required", "1"))
        agg_fn = parse_aggregation(agg_spec)

        source_map = fetch_for_feeds(feeds)
        out: Dict[str, Dict] = {}
        for f in feeds:
            vals = list(source_map.get(f, {}).values())
            if len(vals) < max(1, required):
                out[f] = {"error": "insufficient sources", "sources": source_map.get(f, {})}
                continue
            try:
                p = float(agg_fn(vals))
                out[f] = {"price": p, "sources": source_map.get(f, {}), "ts": int(time.time())}
            except Exception:
                out[f] = {"error": "aggregation failed", "sources": source_map.get(f, {})}
        return jsonify(out)

    return app


def run_price_service(config_ref: str = None, host: str = None, port: int = None):
    cfg = load_config(config_ref) if config_ref else {}
    # Do not apply env globally for service; keep it self-contained
    server_cfg = cfg.get("server", {})
    h = host or server_cfg.get("host", "127.0.0.1")
    p = int(port or server_cfg.get("port", 8787))
    app = build_app(cfg)
    app.run(host=h, port=p)


