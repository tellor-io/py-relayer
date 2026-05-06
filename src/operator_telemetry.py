from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse


def _short_hex(value: str | None, keep: int = 10) -> str | None:
    if not value:
        return value
    value = str(value)
    if len(value) <= keep * 2 + 2:
        return value
    if value.startswith("0x"):
        core = value[2:]
        return f"0x{core[:keep]}...{core[-keep:]}"
    return f"{value[:keep]}...{value[-keep:]}"


def _network_label() -> str:
    evm_network = os.getenv("EVM_NETWORK")
    if evm_network:
        return evm_network
    provider_url = os.getenv("WEB3_PROVIDER_URL")
    if provider_url:
        try:
            parsed = urlparse(provider_url)
            return parsed.hostname or "direct-web3"
        except Exception:
            return "direct-web3"
    return "unknown"


def _feed_label() -> str:
    return os.getenv("FEED_NAME") or os.getenv("QUERY_STRING") or _short_hex(os.getenv("QUERY_ID")) or "unknown"


def _base_payload(event_type: str) -> dict:
    return {
        "ts": time.time(),
        "event": event_type,
        "network": _network_label(),
        "feed": _feed_label(),
        "mode": os.getenv("RELAYER_MODE") or os.getenv("MODE"),
        "query_id": os.getenv("QUERY_ID"),
        "query_data": _short_hex(os.getenv("QUERY_DATA"), keep=16),
        "data_bridge_address": os.getenv("DATA_BRIDGE_ADDRESS"),
        "layer_user_address": os.getenv("LAYER_USER_ADDRESS"),
        "layer_tx_creator_address": os.getenv("LAYER_TX_CREATOR_ADDRESS"),
    }


def emit_operator_event(event_type: str, **fields) -> None:
    """
    Optional structured telemetry for production operations.

    Set RELAYER_OPERATOR_EVENT_LOG to append JSONL events and/or RELAYER_HEALTH_DIR
    to atomically maintain one latest-health JSON file per relayer.
    """
    event_log = os.getenv("RELAYER_OPERATOR_EVENT_LOG")
    health_dir = os.getenv("RELAYER_HEALTH_DIR")
    if not event_log and not health_dir:
        return

    payload = _base_payload(event_type)
    payload.update(fields)

    try:
        if event_log:
            path = Path(event_log)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, sort_keys=True) + "\n")

        if health_dir:
            directory = Path(health_dir)
            directory.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", f"relayer-{payload['network']}-{payload['feed']}")
            target = directory / f"{safe_name}.json"
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
                temp_name = f.name
            os.replace(temp_name, target)
    except Exception:
        # Telemetry must never interrupt relaying.
        return
