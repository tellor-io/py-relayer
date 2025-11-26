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
from src.price_providers.sushiswap import SushiKatanaProvider
from src.price_aggregation import median, trimmed_mean
from src.logger_utils import get_logger
from src.custom_feeds import HANDLERS
from src.evm_rpc import EvmRpcResolver


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
    logger = get_logger(__name__)
    server_cfg = service_cfg.get("server", {})
    cache_ttl = int(server_cfg.get("cache_ttl_secs", 10))
    cache = InMemoryCache(ttl_seconds=cache_ttl)

    providers_cfg = service_cfg.get("providers", {})
    providers = {}
    logger.debug(f"price-service starting with cache_ttl_secs={cache_ttl}")
    # CoinGecko
    cg_cfg = providers_cfg.get("coingecko", {})
    if cg_cfg.get("enabled", True):
        providers["coingecko"] = CoinGeckoProvider(
            base_url=cg_cfg.get("base_url", "https://api.coingecko.com/api/v3/simple/price"),
            rpm=int(cg_cfg.get("rpm", 50)),
        )
        logger.debug(f"provider enabled: coingecko base={cg_cfg.get('base_url')} rpm={cg_cfg.get('rpm')}")
    # CoinMarketCap
    cmc_cfg = providers_cfg.get("coinmarketcap", {})
    if cmc_cfg.get("enabled", False) and cmc_cfg.get("api_key"):
        providers["coinmarketcap"] = CoinMarketCapProvider(
            base_url=cmc_cfg.get("base_url", "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"),
            api_key=os.path.expandvars(cmc_cfg.get("api_key")),
            rpm=int(cmc_cfg.get("rpm", 30)),
        )
        logger.debug("provider enabled: coinmarketcap")
    # CoinPaprika
    paprika_cfg = providers_cfg.get("coinpaprika", {})
    if paprika_cfg.get("enabled", False):
        providers["coinpaprika"] = CoinPaprikaProvider(
            base_url=paprika_cfg.get("base_url", "https://api.coinpaprika.com/v1"),
            rpm=int(paprika_cfg.get("rpm", 30)),
        )
        logger.debug("provider enabled: coinpaprika")
    # Coinbase spot
    coinbase_cfg = providers_cfg.get("coinbase", {})
    if coinbase_cfg.get("enabled", False):
        providers["coinbase"] = CoinbaseProvider(
            base_url=coinbase_cfg.get("base_url", "https://api.coinbase.com/v2"),
            rpm=int(coinbase_cfg.get("rpm", 60)),
        )
        logger.debug("provider enabled: coinbase")
    # Curve price API (per address)
    curve_cfg = providers_cfg.get("curve", {})
    if curve_cfg.get("enabled", False):
        providers["curve"] = CurvePriceApiProvider(
            base_url=curve_cfg.get("base_url", "https://prices.curve.fi/v1/usd_price/ethereum"),
            rpm=int(curve_cfg.get("rpm", 60)),
        )
        logger.debug("provider enabled: curve")
    # Sushi Katana
    sushi_cfg = providers_cfg.get("sushiswap", {})
    if sushi_cfg.get("enabled", False):
        providers["sushiswap"] = SushiKatanaProvider(
            base_url=sushi_cfg.get("base_url", "https://api.sushi.com/price/v1/747474"),
            rpm=int(sushi_cfg.get("rpm", 60)),
        )
        logger.debug("provider enabled: sushiswap")

    feeds_cfg = service_cfg.get("feeds", [])
    feed_map: Dict[str, Dict[str, str]] = {}
    for f in feeds_cfg:
        name = f.get("name")
        if not name:
            continue
        feed_map[name] = f

    # Prepare EVM networks resolver (optional)
    evm_cfg_ref = server_cfg.get("evm_networks_config") or os.environ.get("EVM_NETWORKS_CONFIG")
    evm_resolver = EvmRpcResolver(evm_cfg_ref) if evm_cfg_ref else None

    app = Flask(__name__)

    def resolve_provider_keys(feed: str) -> Tuple[str, Dict[str, str]]:
        f = feed_map.get(feed, {})
        quote = f.get("quote", "usd").lower()
        keys = {}
        if "coingecko" in providers and f.get("coingecko_id"):
            keys["coingecko"] = f["coingecko_id"].lower()
        if "coinmarketcap" in providers and f.get("coinmarketcap_id"):
            keys["coinmarketcap"] = f["coinmarketcap_id"].upper()
        if "coinpaprika" in providers and f.get("coinpaprika_id"):
            keys["coinpaprika"] = f["coinpaprika_id"].lower()
        if "coinbase" in providers and f.get("coinbase_pair"):
            keys["coinbase"] = f["coinbase_pair"].upper()  # e.g., ETH-USD
        if "curve" in providers and f.get("curve_address"):
            keys["curve"] = f["curve_address"].lower()
        logger.debug(f"resolve keys feed={feed} quote={quote} keys={keys}")
        return quote, keys

    def fetch_for_feeds(feeds: List[str]) -> Dict[str, Dict]:
        logger.debug(f"batch fetch start feeds={feeds}")
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
                if cached_values:
                    logger.debug(f"cache hits provider={prov} quote={quote} hits={list(cached_values.keys())}")
                if missing:
                    logger.debug(f"cache miss provider={prov} quote={quote} missing={missing}")
                # Batch fetch remaining
                fetched: Dict[str, float] = {}
                if missing:
                    data, err = provider.batch_fetch(missing, quote)
                    if not err and data:
                        fetched = data
                        for asset, price in data.items():
                            cache.set(prov, asset, quote, price)
                        logger.debug(f"provider fetched provider={prov} quote={quote} data={data}")
                    else:
                        logger.debug(f"provider fetch error provider={prov} err={err}")
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
        logger.debug(f"batch fetch complete results={results}")

        return results

    @app.get("/price")
    def get_price():
        feed = request.args.get("feed")
        if not feed:
            return jsonify({"error": "missing feed"}), 400
        agg_spec = request.args.get("agg", "median")
        required = int(request.args.get("required", "1"))
        agg_fn = parse_aggregation(agg_spec)
        logger.debug(f"GET /price feed={feed} agg={agg_spec} required={required}")

        fcfg = feed_map.get(feed, {})
        handler_key = fcfg.get("handler")
        if handler_key:
            handler = HANDLERS.get(handler_key)
            if not handler:
                return jsonify({"error": f"unknown handler '{handler_key}'"}), 400
            try:
                if handler_key and evm_resolver is None:
                    # Some handlers may require EVM access.
                    logger.debug("handler requested without evm_resolver configured")
                result = handler.fetch(fcfg, lambda fs: fetch_for_feeds(fs), agg_fn, evm_resolver)
                return jsonify({"feed": feed, **result})
            except Exception as e:
                logger.debug(f"handler error feed={feed} handler={handler_key} err={e}")
                return jsonify({"error": f"handler error: {e}"}), 424
        # standard path
        data = fetch_for_feeds([feed]).get(feed, {})
        values = list(data.values())
        if len(values) < max(1, required):
            logger.debug(f"/price insufficient sources feed={feed} sources={data}")
            return jsonify({"error": "insufficient sources", "sources": data}), 424
        try:
            price = float(agg_fn(values))
        except Exception:
            logger.debug(f"/price aggregation failed feed={feed} sources={data}")
            return jsonify({"error": "aggregation failed", "sources": data}), 422
        logger.debug(f"/price result feed={feed} price={price} sources={data}")
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

        logger.debug(f"GET /batch feeds={feeds} agg={agg_spec} required={required}")
        source_map = fetch_for_feeds(feeds)
        out: Dict[str, Dict] = {}
        for f in feeds:
            vals = list(source_map.get(f, {}).values())
            fcfg = feed_map.get(f, {})
            handler_key = fcfg.get("handler")
            if handler_key:
                handler = HANDLERS.get(handler_key)
                if not handler:
                    out[f] = {"error": f"unknown handler '{handler_key}'", "sources": source_map.get(f, {})}
                    continue
                try:
                    result = handler.fetch(fcfg, lambda fs: fetch_for_feeds(fs), agg_fn, evm_resolver)
                    out[f] = result
                    continue
                except Exception as e:
                    out[f] = {"error": f"handler error: {e}", "sources": source_map.get(f, {})}
                    continue
            if len(vals) < max(1, required):
                logger.debug(f"/batch insufficient sources feed={f} sources={source_map.get(f, {})}")
                out[f] = {"error": "insufficient sources", "sources": source_map.get(f, {})}
                continue
            try:
                p = float(agg_fn(vals))
                out[f] = {"price": p, "sources": source_map.get(f, {}), "ts": int(time.time())}
            except Exception:
                logger.debug(f"/batch aggregation failed feed={f} sources={source_map.get(f, {})}")
                out[f] = {"error": "aggregation failed", "sources": source_map.get(f, {})}
        logger.debug(f"/batch result out={out}")
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


