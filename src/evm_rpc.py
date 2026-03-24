import os
import threading
import time
from typing import Any, Dict, List, Optional

from urllib.parse import urlparse
from web3 import Web3
from web3.providers.rpc import HTTPProvider

from src.config_loader import load_config
from src.logger_utils import get_logger


logger = get_logger(__name__)

def _redact_rpc_url(url: str) -> str:
    """
    Redact API keys / paths from RPC URLs for safe logging.
    Keeps only scheme://host[:port]
    """
    try:
        p = urlparse(url)
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        scheme = p.scheme or "http"
        return f"{scheme}://{host}{port}"
    except Exception:
        return "<redacted>"


class _NetworkState:
    def __init__(self, urls: List[str], reset_interval_secs: int, health_timeout_ms: int, error_threshold: int):
        self.urls = urls
        self.reset_interval_secs = reset_interval_secs
        self.health_timeout_ms = health_timeout_ms
        self.error_threshold = error_threshold
        self.current_provider_index = 0
        self.last_switch_time = 0.0
        self.consecutive_errors = 0
        self.lock = threading.Lock()


class EvmRpcResolver:
    """
    Resolves Web3 instances for a named EVM network with provider fallback and
    timed reset to the top-preference provider.
    """

    def __init__(self, config_ref: Optional[str] = None):
        # Determine config reference
        ref = config_ref or os.environ.get("EVM_NETWORKS_CONFIG", "evm-networks")
        self._config_ref = ref
        self._networks: Dict[str, _NetworkState] = {}
        self._load_networks()

    def _load_networks(self) -> None:
        cfg = load_config(self._config_ref) if self._config_ref else {}
        # top-level keys are network names (e.g., "ethereum") with nested fields
        for name, net in cfg.items():
            if not isinstance(net, dict):
                continue
            urls = [u for u in net.get("rpcs", []) if isinstance(u, str) and u]
            if not urls:
                continue
            reset_interval_secs = int(net.get("reset_interval_secs", 3600))
            health_timeout_ms = int(net.get("health_timeout_ms", 3000))
            error_threshold = int(net.get("error_threshold", 1))
            self._networks[name] = _NetworkState(urls, reset_interval_secs, health_timeout_ms, error_threshold)
            logger.debug(f"evm network loaded name={name} urls={len(urls)} reset={reset_interval_secs}s")

    def _attempt_connect(self, url: str, timeout_ms: int) -> Optional[Web3]:
        try:
            provider = HTTPProvider(endpoint_uri=url, request_kwargs={"timeout": timeout_ms / 1000.0})
            w3 = Web3(provider)
            if w3.is_connected():
                return w3
            return None
        except Exception as e:
            logger.debug(f"RPC connect failed url={url} err={e}")
            return None

    def get_web3(self, network: str) -> Web3:
        ns = self._networks.get(network)
        if ns is None:
            raise RuntimeError(f"Unknown EVM network: {network}")

        with ns.lock:
            now = time.time()
            try_from_top = (now - ns.last_switch_time) >= ns.reset_interval_secs

            # Always attempt from top when try_from_top is True or when we have errors
            start_indices = list(range(0, len(ns.urls))) if try_from_top else [ns.current_provider_index] + [i for i in range(0, len(ns.urls)) if i != ns.current_provider_index]

            for idx in start_indices:
                url = ns.urls[idx]
                w3 = self._attempt_connect(url, ns.health_timeout_ms)
                if w3 is not None:
                    if try_from_top or idx != ns.current_provider_index:
                        ns.last_switch_time = now
                        ns.current_provider_index = idx
                        ns.consecutive_errors = 0
                        logger.info(f"EVM RPC selected network={network} url={_redact_rpc_url(url)}")
                    return w3

            # None connected
            raise RuntimeError(f"No healthy RPC endpoint for network {network}")

    def call_with_web3(self, network: str, fn):
        ns = self._networks.get(network)
        if ns is None:
            raise RuntimeError(f"Unknown EVM network: {network}")
        # initial attempt
        try:
            w3 = self.get_web3(network)
            return fn(w3)
        except Exception as e:
            logger.debug(f"RPC call error on network={network}: {e}")
            with ns.lock:
                ns.consecutive_errors += 1
                ns.last_switch_time = 0.0  # force try-from-top next time
            # retry once with fresh provider from top-of-list
            w3 = self.get_web3(network)
            return fn(w3)


