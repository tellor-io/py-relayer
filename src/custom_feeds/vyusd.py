import time
from typing import Any, Callable, Dict

from web3 import Web3

from src.custom_feeds.base import CustomFeedHandler


class VyusdUsdHandler(CustomFeedHandler):
    def fetch(
        self,
        feed_cfg: Dict[str, Any],
        fetch_for_feeds: Callable[[list[str]], Dict[str, Dict[str, float]]],
        agg_fn: Callable[[list[float]], float],
        evm_resolver: Any,
    ) -> Dict[str, Any]:
        contract_addr = feed_cfg.get("vyusd_contract")
        network = feed_cfg.get("evm_network")
        usdc_feed = feed_cfg.get("usdc_feed", "usdc-usd")
        if not contract_addr or not network:
            raise Exception("vyusd config missing vyusd_contract or evm_network")

        def _read_exchange_rate(w3: Web3) -> float:
            abi = [
                {
                    "constant": True,
                    "inputs": [],
                    "name": "exchangeRateScaled",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function",
                }
            ]
            contract = w3.eth.contract(address=contract_addr, abi=abi)
            raw_rate = contract.functions.exchangeRateScaled().call()
            return float(raw_rate) / 1e18

        conv = evm_resolver.call_with_web3(network, _read_exchange_rate)

        # Fetch USDC price via standard aggregator
        sources_map = fetch_for_feeds([usdc_feed])
        usdc_sources = sources_map.get(usdc_feed, {})
        if not usdc_sources:
            raise Exception("insufficient USDC sources for vyusd; configure usdc-usd providers")
        usdc_vals = list(usdc_sources.values())
        usdc_price = float(agg_fn(usdc_vals))
        final_price = conv / usdc_price

        sources_out = dict(usdc_sources)
        sources_out["vyusd_conversion"] = conv

        return {"price": final_price, "sources": sources_out, "ts": int(time.time())}


