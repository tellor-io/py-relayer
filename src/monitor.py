from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from eth_abi import decode
from eth_utils import decode_hex
from web3 import Web3

from src import config_loader
from src.evm_rpc import EvmRpcResolver
from src.query_parser import QueryParser


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
LOG_TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (?P<level>[A-Z]+) - (?P<msg>.*?)(?: module=|$)"
)
STATUS_RE = re.compile(
    r"Status mode=(?P<mode>\S+) query_id=(?P<query_id>\S+) query_data=(?P<query_data>\S+) "
    r"cycle_list=(?P<cycle_list>\S+) report_age_s=(?P<report_age_s>\S+) "
    r"consensus_age_s=(?P<consensus_age_s>\S+) next_heartbeat_in_s=(?P<next_heartbeat_in_s>\S+) "
    r"api_price_age_s=(?P<api_price_age_s>\S+) should_tip=(?P<should_tip>\S+) should_relay=(?P<should_relay>\S+)"
)
CONFIG_RE = re.compile(
    r"Config heartbeat_interval_s=(?P<heartbeat_interval_s>\S+) offset_s=(?P<offset_s>\S+) "
    r"check_interval_s=(?P<check_interval_s>\S+) price_threshold_pct=(?P<price_threshold_pct>\S+) "
    r"optimistic_delay_s=(?P<optimistic_delay_s>\S+) max_attestation_age_s=(?P<max_attestation_age_s>\S+) "
    r"max_data_age_s=(?P<max_data_age_s>\S+) min_stake_pct=(?P<min_stake_pct>\S+)"
)
START_RE = re.compile(
    r"Starting threshold relayer mode=(?P<mode>\S+) query_id=(?P<query_id>\S+) "
    r"query_data=(?P<query_data>\S+) contract_type=(?P<contract_type>\S+)"
)
LAYER_REPORT_RE = re.compile(
    r"Relaying Layer report query_id=(?P<query_id>\S+) report_ts_ms=(?P<report_ts_ms>\d+) "
    r"attestation_ts_ms=(?P<attestation_ts_ms>\d+) age_s=(?P<age_s>[-.\d]+) "
    r"power=(?P<power>\S+) last_consensus_ms=(?P<last_consensus_ms>\S+)"
)
EVM_RECEIPT_RE = re.compile(
    r"(?P<operation>.+) transaction successful! Block: (?P<block>\d+), Gas used: (?P<gas_used>\d+)"
)
VALSET_UPDATE_RE = re.compile(
    r"Updating validator set source_ts=(?P<source_ts>\d+) target_ts=(?P<target_ts>\d+) "
    r"signed_power=(?P<signed_power>\d+) threshold=(?P<threshold>\d+)"
)
TX_HASH_RE = re.compile(r"(?:tx:|Txhash:|receipt:)\s*(?P<hash>0x[a-fA-F0-9]{64}|[a-fA-F0-9]{64})")


ERROR_PATTERNS = {
    "unexpected_error": "Unexpected error",
    "layer_status_issue": "Layer chain status issue",
    "oracle_not_relayed": "Oracle data not relayed",
    "evm_tx_attempt_failed": "Transaction attempt",
    "evm_tx_failed": "transaction FAILED",
    "layer_tx_not_confirmed": "Layer transaction not confirmed",
    "layer_tx_failed": "FAILED with code",
    "no_reachable_valset": "No reachable validator-set relay",
    "checkpoint_mismatch": "Checkpoint mismatch",
    "insufficient_attestation_power": "Insufficient attestation power",
    "request_attestations": "requesting attestations",
    "nonce_conflict": "Nonce conflict",
    "sequence_conflict": "Sequence conflict",
    "rpc_rate_limit": "Rate limit",
}


@dataclass
class Alert:
    severity: str
    code: str
    message: str
    action: str


@dataclass
class FeedConfig:
    network: str
    feed: str
    config_path: str
    session_name: str
    log_path: str
    mode: str
    query_id: Optional[str]
    query_data: Optional[str]
    layer_swagger_endpoint: Optional[str]
    layer_rpc_endpoint: Optional[str]
    evm_network: Optional[str]
    web3_provider_url: Optional[str]
    data_bridge_address: Optional[str]
    layer_user_address: Optional[str]
    layer_tx_creator_address: Optional[str]
    heartbeat_interval_s: int
    check_interval_s: int
    optimistic_delay_s: int
    max_attestation_age_s: int
    max_data_age_s: int
    min_stake_pct: int
    price_threshold: float
    price_source: Optional[str]
    price_service_url: Optional[str]


@dataclass
class LogSummary:
    exists: bool
    path: str
    size_bytes: int = 0
    mtime: Optional[float] = None
    newest_parsed_ts: Optional[float] = None
    last_status: Optional[dict[str, Any]] = None
    last_config: Optional[dict[str, Any]] = None
    last_startup: Optional[dict[str, Any]] = None
    last_tip: Optional[dict[str, Any]] = None
    last_relay: Optional[dict[str, Any]] = None
    last_layer_report: Optional[dict[str, Any]] = None
    last_evm_receipt: Optional[dict[str, Any]] = None
    last_valset_update: Optional[dict[str, Any]] = None
    last_layer_tx_hash: Optional[str] = None
    last_evm_tx_hash: Optional[str] = None
    counts: dict[str, int] = field(default_factory=dict)
    recent_events: list[dict[str, Any]] = field(default_factory=list)


class JsonError(Exception):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _strip_0x(value: str) -> str:
    return value[2:] if value.startswith("0x") else value


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "None":
            return default
        return int(float(value))
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "None":
            return default
        return float(value)
    except Exception:
        return default


def _clean_line(line: str) -> str:
    return ANSI_RE.sub("", line).rstrip("\n")


def _parse_log_ts(line: str) -> tuple[Optional[float], str]:
    match = LOG_TS_RE.match(line)
    if not match:
        return None, line
    ts = None
    try:
        dt = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        ts = dt.timestamp()
    except Exception:
        pass
    return ts, match.group("msg")


def _event(event_type: str, message: str, ts: Optional[float], **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"type": event_type, "message": message}
    if ts is not None:
        data["ts"] = ts
    data.update(extra)
    return data


def _tail_lines(path: Path, max_bytes: int) -> list[str]:
    if max_bytes <= 0:
        return []
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        data = f.read()
    return data.decode("utf-8", errors="replace").splitlines()


def parse_log_file(path: Path, max_bytes: int = 512 * 1024) -> LogSummary:
    summary = LogSummary(exists=path.exists(), path=str(path), counts={k: 0 for k in ERROR_PATTERNS})
    if not path.exists():
        return summary

    stat = path.stat()
    summary.size_bytes = stat.st_size
    summary.mtime = stat.st_mtime

    for raw_line in _tail_lines(path, max_bytes):
        line = _clean_line(raw_line)
        ts, msg = _parse_log_ts(line)
        if ts is not None:
            summary.newest_parsed_ts = ts

        for key, needle in ERROR_PATTERNS.items():
            if needle in msg:
                summary.counts[key] = summary.counts.get(key, 0) + 1

        status_match = STATUS_RE.search(msg)
        if status_match:
            data = status_match.groupdict()
            summary.last_status = {
                "mode": data["mode"],
                "query_id": data["query_id"],
                "query_data": data["query_data"],
                "cycle_list": data["cycle_list"] == "True",
                "report_age_s": None if data["report_age_s"] == "None" else _to_int(data["report_age_s"]),
                "consensus_age_s": None if data["consensus_age_s"] == "None" else _to_int(data["consensus_age_s"]),
                "next_heartbeat_in_s": None
                if data["next_heartbeat_in_s"] == "None"
                else _to_int(data["next_heartbeat_in_s"]),
                "api_price_age_s": None if data["api_price_age_s"] == "None" else _to_int(data["api_price_age_s"]),
                "should_tip": data["should_tip"] == "True",
                "should_relay": data["should_relay"] == "True",
                "ts": ts,
            }
            summary.recent_events.append(_event("status", msg, ts, **summary.last_status))
            continue

        config_match = CONFIG_RE.search(msg)
        if config_match:
            summary.last_config = {
                key: _to_float(value) if "." in value else _to_int(value)
                for key, value in config_match.groupdict().items()
            }
            summary.recent_events.append(_event("config", msg, ts, **summary.last_config))
            continue

        startup_match = START_RE.search(msg)
        if startup_match:
            summary.last_startup = startup_match.groupdict()
            summary.recent_events.append(_event("startup", msg, ts, **summary.last_startup))
            continue

        layer_report_match = LAYER_REPORT_RE.search(msg)
        if layer_report_match:
            data = layer_report_match.groupdict()
            summary.last_layer_report = {
                "query_id": data["query_id"],
                "report_ts_ms": _to_int(data["report_ts_ms"]),
                "attestation_ts_ms": _to_int(data["attestation_ts_ms"]),
                "age_s": _to_float(data["age_s"]),
                "power": data["power"],
                "last_consensus_ms": data["last_consensus_ms"],
                "ts": ts,
            }
            summary.recent_events.append(_event("layer_report", msg, ts, **summary.last_layer_report))
            continue

        receipt_match = EVM_RECEIPT_RE.search(msg)
        if receipt_match:
            data = receipt_match.groupdict()
            summary.last_evm_receipt = {
                "operation": data["operation"],
                "block": _to_int(data["block"]),
                "gas_used": _to_int(data["gas_used"]),
                "ts": ts,
            }
            summary.recent_events.append(_event("evm_receipt", msg, ts, **summary.last_evm_receipt))
            continue

        valset_match = VALSET_UPDATE_RE.search(msg)
        if valset_match:
            summary.last_valset_update = {key: _to_int(value) for key, value in valset_match.groupdict().items()}
            summary.last_valset_update["ts"] = ts
            summary.recent_events.append(_event("valset_update", msg, ts, **summary.last_valset_update))
            continue

        tx_match = TX_HASH_RE.search(msg)
        if tx_match:
            tx_hash = tx_match.group("hash")
            if "Layer transaction" in msg or "Transaction broadcast" in msg:
                summary.last_layer_tx_hash = tx_hash
                summary.recent_events.append(_event("layer_tx", msg, ts, tx_hash=tx_hash))
            else:
                summary.last_evm_tx_hash = tx_hash
                summary.recent_events.append(_event("evm_tx", msg, ts, tx_hash=tx_hash))

        if "Action tip" in msg:
            summary.last_tip = {"message": msg, "ts": ts}
            summary.recent_events.append(_event("tip", msg, ts))
        elif "Action relay" in msg:
            summary.last_relay = {"message": msg, "ts": ts}
            summary.recent_events.append(_event("relay", msg, ts))
        elif "Oracle data relay successful" in msg:
            summary.recent_events.append(_event("relay_success", msg, ts))
        elif "New data received after tip" in msg:
            summary.recent_events.append(_event("tip_report_received", msg, ts))

    summary.recent_events = summary.recent_events[-50:]
    return summary


def discover_screen_sessions() -> dict[str, str]:
    try:
        result = subprocess.run(["screen", "-ls"], capture_output=True, text=True, timeout=5)
    except Exception as exc:
        return {"__error__": str(exc)}

    sessions: dict[str, str] = {}
    for line in result.stdout.splitlines() + result.stderr.splitlines():
        match = re.search(r"(?:\d+\.)?(relayer-[^\s]+)", line)
        if match:
            sessions[match.group(1)] = line.strip()
    return sessions


def _resolve_query(repo_root: Path, command_cfg: dict[str, Any], env_cfg: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    query_id = command_cfg.get("query_id") or env_cfg.get("QUERY_ID")
    query_data = command_cfg.get("query_data") or env_cfg.get("QUERY_DATA")
    query_string = command_cfg.get("query_string") or env_cfg.get("QUERY_STRING")
    if query_string and (not query_id or not query_data):
        parser_logger = logging.getLogger("src.query_parser")
        old_level = parser_logger.level
        parser_logger.setLevel(logging.WARNING)
        try:
            parser = QueryParser(query_types_dir=str(repo_root / "query-types"))
            info = parser.get_query_info(str(query_string))
        finally:
            parser_logger.setLevel(old_level)
        query_id = query_id or info["queryId"]
        query_data = query_data or info["queryData"]
    return str(query_id) if query_id else None, str(query_data) if query_data else None


def load_feed_configs(
    repo_root: Path,
    configs_dir: Path,
    logs_dir: Path,
    networks: tuple[str, ...] = (),
    exclude_backups: bool = False,
) -> list[FeedConfig]:
    config_loader.DEFAULT_SEARCH_ROOT = configs_dir
    network_filter = set(networks)
    feeds: list[FeedConfig] = []

    for network_dir in sorted(configs_dir.iterdir()):
        if not network_dir.is_dir():
            continue
        network = network_dir.name
        if network.endswith("-shared"):
            continue
        if exclude_backups and network.endswith("-backup"):
            continue
        if network_filter and network not in network_filter:
            continue

        for path in sorted(network_dir.glob("*.toml")):
            if path.name == "backup-template.toml" or path.name.endswith("-shared.toml"):
                continue
            cfg = config_loader.load_config(str(path))
            env_cfg = cfg.get("env", {}) or {}
            command_cfg = (cfg.get("commands", {}) or {}).get("relay-threshold", {}) or {}
            query_id, query_data = _resolve_query(repo_root, command_cfg, env_cfg)
            feed = path.stem
            session_name = f"relayer-{network}-{feed}"
            mode = "backup" if network.endswith("-backup") or bool(command_cfg.get("backup")) else "primary"

            feeds.append(
                FeedConfig(
                    network=network,
                    feed=feed,
                    config_path=str(path),
                    session_name=session_name,
                    log_path=str(logs_dir / f"{session_name}.log"),
                    mode=mode,
                    query_id=query_id,
                    query_data=query_data,
                    layer_swagger_endpoint=env_cfg.get("LAYER_SWAGGER_ENDPOINT"),
                    layer_rpc_endpoint=env_cfg.get("LAYER_RPC_ENDPOINT"),
                    evm_network=env_cfg.get("EVM_NETWORK"),
                    web3_provider_url=env_cfg.get("WEB3_PROVIDER_URL"),
                    data_bridge_address=env_cfg.get("DATA_BRIDGE_ADDRESS"),
                    layer_user_address=env_cfg.get("LAYER_USER_ADDRESS"),
                    layer_tx_creator_address=env_cfg.get("LAYER_TX_CREATOR_ADDRESS"),
                    heartbeat_interval_s=_to_int(command_cfg.get("sleep_time", env_cfg.get("SLEEP_TIME")), 600),
                    check_interval_s=_to_int(command_cfg.get("check_interval", env_cfg.get("CHECK_INTERVAL")), 300),
                    optimistic_delay_s=_to_int(command_cfg.get("optimistic_delay"), 43200),
                    max_attestation_age_s=_to_int(command_cfg.get("max_attestation_age"), 600),
                    max_data_age_s=_to_int(command_cfg.get("max_data_age"), 86400),
                    min_stake_pct=_to_int(command_cfg.get("min_stake_percentage"), 33),
                    price_threshold=_to_float(command_cfg.get("price_threshold"), 0.01),
                    price_source=env_cfg.get("PRICE_SOURCE"),
                    price_service_url=env_cfg.get("PRICE_SERVICE_URL"),
                )
            )
    return feeds


class LayerProbe:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._cache: dict[str, Any] = {}

    def _get_json(self, url: str) -> Any:
        if url in self._cache:
            return self._cache[url]
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            self._cache[url] = data
            return data
        except Exception as exc:
            raise JsonError(str(exc)) from exc

    def status(self, rpc_endpoint: Optional[str]) -> dict[str, Any]:
        if not rpc_endpoint:
            return {"ok": False, "error": "missing Layer RPC endpoint"}
        try:
            data = self._get_json(rpc_endpoint.rstrip("/") + "/status")
            sync_info = data.get("result", {}).get("sync_info", {})
            latest_block_time = sync_info.get("latest_block_time")
            block_age_s = None
            if latest_block_time:
                parsed = datetime.fromisoformat(latest_block_time.replace("Z", "+00:00"))
                block_age_s = time.time() - parsed.timestamp()
            catching_up = sync_info.get("catching_up")
            catching_up_bool = catching_up is True or str(catching_up).lower() == "true"
            return {
                "ok": not catching_up_bool and (block_age_s is None or block_age_s <= 60),
                "catching_up": catching_up_bool,
                "latest_block_height": _to_int(sync_info.get("latest_block_height")),
                "latest_block_time": latest_block_time,
                "block_age_s": block_age_s,
                "chain_id": data.get("result", {}).get("node_info", {}).get("network"),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def rest(self, swagger_endpoint: Optional[str], path: str) -> Any:
        if not swagger_endpoint:
            raise JsonError("missing Layer swagger endpoint")
        return self._get_json(swagger_endpoint.rstrip("/") + path)

    def feed_state(self, feed: FeedConfig) -> dict[str, Any]:
        state: dict[str, Any] = {"status": self.status(feed.layer_rpc_endpoint)}
        now_ms = int(time.time() * 1000)

        try:
            valset_ts_data = self.rest(feed.layer_swagger_endpoint, "/layer/bridge/get_current_validator_set_timestamp")
            layer_valset_ts = _to_int(valset_ts_data.get("timestamp"))
            state["latest_validator_timestamp"] = layer_valset_ts
            if layer_valset_ts:
                checkpoint = self.rest(
                    feed.layer_swagger_endpoint,
                    f"/layer/bridge/get_validator_checkpoint_params/{layer_valset_ts}",
                )
                state["current_power_threshold"] = _to_int(checkpoint.get("power_threshold"))
                state["validator_checkpoint"] = checkpoint.get("checkpoint")
        except Exception as exc:
            state["valset_error"] = str(exc)

        if feed.query_id:
            query_id = _strip_0x(feed.query_id)
            try:
                report = self.rest(
                    feed.layer_swagger_endpoint,
                    f"/tellor-io/layer/oracle/get_data_before/{query_id}/{now_ms}",
                )
                state["latest_report"] = report
                report_ts_ms = _to_int(report.get("timestamp"))
                if report_ts_ms:
                    state["report_age_s"] = (now_ms - report_ts_ms) / 1000.0
                    snapshots = self.rest(
                        feed.layer_swagger_endpoint,
                        f"/layer/bridge/get_snapshots_by_report/{query_id}/{report_ts_ms}",
                    )
                    snapshot_list = snapshots.get("snapshots") or []
                    state["snapshot_count"] = len(snapshot_list)
                    if snapshot_list:
                        snapshot = snapshot_list[-1]
                        state["latest_snapshot"] = snapshot
                        attest_data = self.rest(
                            feed.layer_swagger_endpoint,
                            f"/layer/bridge/get_attestation_data_by_snapshot/{snapshot}",
                        )
                        state["attestation_data"] = attest_data
                        att_ts_ms = _to_int(attest_data.get("attestation_timestamp") or attest_data.get("timestamp"))
                        last_consensus_ms = _to_int(attest_data.get("last_consensus_timestamp"))
                        if att_ts_ms:
                            state["attestation_age_s"] = (now_ms - att_ts_ms) / 1000.0
                        if last_consensus_ms:
                            state["consensus_age_s"] = (now_ms - last_consensus_ms) / 1000.0
            except Exception as exc:
                state["feed_error"] = str(exc)

        if feed.query_data:
            try:
                tip = self.rest(
                    feed.layer_swagger_endpoint,
                    f"/tellor-io/layer/oracle/get_current_tip/{_strip_0x(feed.query_data)}",
                )
                state["current_tip"] = tip
            except Exception as exc:
                state["tip_error"] = str(exc)

        if feed.layer_tx_creator_address and "${" not in feed.layer_tx_creator_address:
            try:
                state["layer_wallet"] = self.rest(
                    feed.layer_swagger_endpoint,
                    f"/cosmos/bank/v1beta1/balances/{feed.layer_tx_creator_address}",
                )
            except Exception as exc:
                state["layer_wallet_error"] = str(exc)

        return state


class EvmProbe:
    def __init__(self, repo_root: Path, timeout: float = 5.0):
        self.repo_root = repo_root
        self.timeout = timeout
        self._web3_cache: dict[str, Web3] = {}
        self._abi_cache: dict[str, Any] = {}

    def _abi(self, name: str) -> Any:
        if name not in self._abi_cache:
            with open(self.repo_root / "abis" / name, "r") as f:
                self._abi_cache[name] = json.load(f)["abi"]
        return self._abi_cache[name]

    def _web3(self, feed: FeedConfig) -> Web3:
        key = feed.web3_provider_url or f"network:{feed.evm_network}"
        if key in self._web3_cache:
            return self._web3_cache[key]
        if feed.web3_provider_url:
            web3 = Web3(Web3.HTTPProvider(feed.web3_provider_url, request_kwargs={"timeout": self.timeout}))
        elif feed.evm_network:
            resolver = EvmRpcResolver(os.environ.get("EVM_NETWORKS_CONFIG"))
            web3 = resolver.get_web3(feed.evm_network)
        else:
            raise RuntimeError("missing WEB3_PROVIDER_URL or EVM_NETWORK")
        self._web3_cache[key] = web3
        return web3

    def feed_state(self, feed: FeedConfig) -> dict[str, Any]:
        state: dict[str, Any] = {}
        try:
            web3 = self._web3(feed)
            state["connected"] = bool(web3.is_connected())
            state["chain_id"] = web3.eth.chain_id
            block = web3.eth.get_block("latest")
            block_ts = _to_int(block.get("timestamp"))
            state["latest_block_number"] = _to_int(block.get("number"))
            state["latest_block_timestamp"] = block_ts
            state["block_age_s"] = time.time() - block_ts if block_ts else None

            if feed.data_bridge_address:
                bridge = web3.eth.contract(
                    address=Web3.to_checksum_address(feed.data_bridge_address),
                    abi=self._abi("TellorDataBridgeTestnet.json"),
                )
                state["bridge"] = {
                    "validator_timestamp": _to_int(bridge.functions.validatorTimestamp().call()),
                    "power_threshold": _to_int(bridge.functions.powerThreshold().call()),
                }
                try:
                    checkpoint = bridge.functions.lastValidatorSetCheckpoint().call()
                    state["bridge"]["checkpoint"] = checkpoint.hex() if hasattr(checkpoint, "hex") else str(checkpoint)
                except Exception as exc:
                    state["bridge"]["checkpoint_error"] = str(exc)

            if feed.layer_user_address and feed.query_id:
                bank = web3.eth.contract(
                    address=Web3.to_checksum_address(feed.layer_user_address),
                    abi=self._abi("TellorDataBank.json"),
                )
                raw_data = bank.functions.getCurrentAggregateData(decode_hex(feed.query_id)).call()
                state["tellor_data_bank"] = self._decode_data_bank(raw_data)

            account = self._evm_account()
            if account:
                state["relayer_wallet"] = {
                    "address": account.address,
                    "balance_wei": web3.eth.get_balance(account.address),
                    "nonce": web3.eth.get_transaction_count(account.address),
                }
        except Exception as exc:
            state["error"] = str(exc)
        return state

    def _evm_account(self) -> Any:
        private_key = os.getenv("ETH_PRIVATE_KEY")
        if not private_key:
            return None
        try:
            from eth_account import Account

            return Account.from_key(private_key)
        except Exception:
            return None

    @staticmethod
    def _decode_data_bank(raw_data: Any) -> dict[str, Any]:
        value: Optional[float] = None
        try:
            if raw_data[0]:
                value = float(decode(["uint256"], raw_data[0])[0]) / 10**18
        except Exception:
            value = None
        aggregate_ts_ms = _to_int(raw_data[2]) if len(raw_data) > 2 else 0
        attestation_ts_ms = _to_int(raw_data[3]) if len(raw_data) > 3 else 0
        relay_ts_s = _to_int(raw_data[4]) if len(raw_data) > 4 else 0
        return {
            "value": value,
            "power": _to_int(raw_data[1]) if len(raw_data) > 1 else 0,
            "aggregate_timestamp_ms": aggregate_ts_ms,
            "attestation_timestamp_ms": attestation_ts_ms,
            "relay_timestamp_s": relay_ts_s,
            "aggregate_age_s": (time.time() - aggregate_ts_ms / 1000) if aggregate_ts_ms else None,
            "relay_age_s": (time.time() - relay_ts_s) if relay_ts_s else None,
        }


def evaluate_alerts(
    feed: FeedConfig,
    screen_running: bool,
    log: LogSummary,
    layer_state: Optional[dict[str, Any]],
    evm_state: Optional[dict[str, Any]],
    now: float,
    status_log_every_s: int,
) -> list[Alert]:
    alerts: list[Alert] = []

    if not screen_running:
        alerts.append(
            Alert("critical", "screen_missing", f"{feed.session_name} is not running", "Restart the feed screen or rerun the start script.")
        )

    if not log.exists:
        alerts.append(Alert("critical", "log_missing", f"{feed.log_path} does not exist", "Check screen startup and tee/log permissions."))
    else:
        latest_log_activity = max(log.mtime or 0, log.newest_parsed_ts or 0)
        stale_after = max(2 * feed.check_interval_s, 2 * status_log_every_s) + 60
        if now - latest_log_activity > stale_after:
            alerts.append(
                Alert(
                    "critical",
                    "log_stale",
                    f"last log activity is {int(now - latest_log_activity)}s old, expected under {stale_after}s",
                    "Attach to the screen and inspect whether the process is blocked.",
                )
            )
        if log.last_status and log.last_status.get("ts") and now - float(log.last_status["ts"]) > stale_after:
            alerts.append(
                Alert(
                    "warning",
                    "status_stale",
                    f"last status snapshot is {int(now - float(log.last_status['ts']))}s old",
                    "Inspect relayer loop health and whether it is stuck inside a chain query.",
                )
            )

    if log.counts.get("evm_tx_failed", 0) or log.counts.get("layer_tx_failed", 0):
        alerts.append(Alert("critical", "tx_failed", "failed Layer or EVM transaction appears in recent logs", "Inspect the tx hash and contract/node error."))
    if log.counts.get("no_reachable_valset", 0):
        alerts.append(Alert("critical", "valset_unreachable", "no reachable validator-set relay found", "Investigate bridge valset signatures and current Layer validator set."))
    if log.counts.get("nonce_conflict", 0) + log.counts.get("sequence_conflict", 0) > 3:
        alerts.append(Alert("warning", "nonce_or_sequence_conflicts", "repeated nonce/sequence conflicts in recent logs", "Check duplicate relayers or competing wallet users."))
    if log.counts.get("rpc_rate_limit", 0) > 3:
        alerts.append(Alert("warning", "rpc_rate_limit", "repeated EVM RPC rate-limit/provider errors", "Check configured RPC providers and failover health."))

    if layer_state:
        status = layer_state.get("status", {})
        if not status.get("ok"):
            alerts.append(Alert("critical", "layer_unhealthy", f"Layer status unhealthy: {status.get('error') or status}", "Inspect Layer RPC/REST endpoint."))
        if _to_float(layer_state.get("report_age_s")) > feed.max_data_age_s:
            alerts.append(Alert("warning", "layer_report_stale", "latest Layer report exceeds max_data_age", "Check tips, reporters, and cycle-list behavior."))
        if _to_float(layer_state.get("attestation_age_s")) > feed.max_attestation_age_s:
            alerts.append(Alert("warning", "attestation_stale", "latest attestation exceeds max_attestation_age", "Check request-attestations flow and bridge module health."))
        if layer_state.get("feed_error"):
            alerts.append(Alert("warning", "layer_feed_query_error", str(layer_state["feed_error"]), "Check query id, REST endpoint, and Layer data availability."))

    if evm_state:
        if evm_state.get("error"):
            alerts.append(Alert("critical", "evm_unhealthy", str(evm_state["error"]), "Inspect EVM RPC config/provider."))
        bridge_ts = _to_int((evm_state.get("bridge") or {}).get("validator_timestamp"))
        layer_ts = _to_int((layer_state or {}).get("latest_validator_timestamp"))
        if layer_ts and bridge_ts and bridge_ts < layer_ts:
            severity = "critical" if log.counts.get("no_reachable_valset", 0) else "warning"
            alerts.append(
                Alert(
                    severity,
                    "bridge_valset_lag",
                    f"EVM bridge validator timestamp {bridge_ts} is behind Layer {layer_ts}",
                    "Inspect valset update logs and bridge signatures.",
                )
            )
        bank = evm_state.get("tellor_data_bank") or {}
        relay_age = _to_float(bank.get("relay_age_s"))
        if relay_age and relay_age > feed.heartbeat_interval_s + max(feed.check_interval_s * 2, 300):
            alerts.append(Alert("critical", "evm_relay_stale", f"EVM relay age is {int(relay_age)}s", "Compare Layer data freshness and relayer decision logs."))

        layer_report = (layer_state or {}).get("attestation_data") or (layer_state or {}).get("latest_report") or {}
        layer_report_ts = _to_int(layer_report.get("timestamp"))
        evm_report_ts = _to_int(bank.get("aggregate_timestamp_ms"))
        if layer_report_ts and evm_report_ts and layer_report_ts > evm_report_ts and relay_age > feed.check_interval_s * 2:
            alerts.append(
                Alert(
                    "warning",
                    "layer_newer_than_evm",
                    f"Layer report {layer_report_ts} is newer than EVM report {evm_report_ts}",
                    "Check whether optimistic delay, attestation age, valset lag, or tx failures explain the gap.",
                )
            )

    return alerts


def summarize_daily(path: Path, lookback_started_at: float) -> dict[str, Any]:
    counts: dict[str, int] = {
        "tip_actions": 0,
        "new_reports_after_tip": 0,
        "relay_actions": 0,
        "relay_successes": 0,
        "evm_receipts": 0,
        "layer_tx_broadcasts": 0,
        "layer_tx_confirmations": 0,
        "valset_updates": 0,
    }
    error_counts: dict[str, int] = {key: 0 for key in ERROR_PATTERNS}
    first_event_ts: Optional[float] = None
    last_event_ts: Optional[float] = None
    last_events: list[dict[str, Any]] = []

    if not path.exists():
        return {
            "lookback_started_at": lookback_started_at,
            "log_exists": False,
            "event_counts": counts,
            "error_counts": {},
            "open_anomalies": ["log file missing"],
        }

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = _clean_line(raw_line)
            ts, msg = _parse_log_ts(line)
            if ts is None or ts < lookback_started_at:
                continue
            first_event_ts = first_event_ts or ts
            last_event_ts = ts

            for key, needle in ERROR_PATTERNS.items():
                if needle in msg:
                    error_counts[key] = error_counts.get(key, 0) + 1

            event_type = None
            if "Action tip" in msg:
                counts["tip_actions"] += 1
                event_type = "tip"
            elif "New data received after tip" in msg:
                counts["new_reports_after_tip"] += 1
                event_type = "tip_report_received"
            elif "Action relay" in msg:
                counts["relay_actions"] += 1
                event_type = "relay"
            elif "Oracle data relay successful" in msg:
                counts["relay_successes"] += 1
                event_type = "relay_success"
            elif EVM_RECEIPT_RE.search(msg):
                counts["evm_receipts"] += 1
                event_type = "evm_receipt"
            elif "Transaction broadcast for" in msg:
                counts["layer_tx_broadcasts"] += 1
                event_type = "layer_tx_broadcast"
            elif "Layer transaction confirmed on-chain" in msg or "confirmed on-chain at height" in msg:
                counts["layer_tx_confirmations"] += 1
                event_type = "layer_tx_confirmed"
            elif VALSET_UPDATE_RE.search(msg):
                counts["valset_updates"] += 1
                event_type = "valset_update"

            if event_type:
                last_events.append(_event(event_type, msg, ts))
                last_events = last_events[-20:]

    open_anomalies: list[str] = []
    if counts["tip_actions"] > counts["new_reports_after_tip"]:
        open_anomalies.append("more tip actions than new Layer reports observed")
    if counts["relay_actions"] > counts["relay_successes"]:
        open_anomalies.append("more relay actions than successful relays observed")
    if counts["layer_tx_broadcasts"] > counts["layer_tx_confirmations"]:
        open_anomalies.append("more Layer tx broadcasts than confirmations observed")
    if any(error_counts.values()):
        open_anomalies.append("recent error patterns found in logs")

    return {
        "lookback_started_at": lookback_started_at,
        "log_exists": True,
        "first_event_ts": first_event_ts,
        "last_event_ts": last_event_ts,
        "event_counts": counts,
        "error_counts": {key: value for key, value in error_counts.items() if value},
        "open_anomalies": open_anomalies,
        "last_events": last_events,
    }


def build_snapshot(
    repo_root: Optional[Path] = None,
    configs_dir: Optional[Path] = None,
    logs_dir: Optional[Path] = None,
    networks: tuple[str, ...] = (),
    exclude_backups: bool = False,
    skip_chain: bool = False,
    skip_evm: bool = False,
    tail_bytes: int = 512 * 1024,
    status_log_every_s: int = 300,
    daily_reconcile: bool = False,
    lookback_hours: int = 24,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    configs = configs_dir or root / "configs"
    logs = logs_dir or root / "logs"
    now = time.time()
    config_loader.DEFAULT_SEARCH_ROOT = configs

    feeds = load_feed_configs(root, configs, logs, networks=networks, exclude_backups=exclude_backups)
    screens = discover_screen_sessions()
    screen_error = screens.pop("__error__", None)
    layer_probe = LayerProbe()
    evm_probe = EvmProbe(root)
    feed_snapshots: list[dict[str, Any]] = []

    for feed in feeds:
        log_summary = parse_log_file(Path(feed.log_path), max_bytes=tail_bytes)
        layer_state = None
        evm_state = None
        if not skip_chain:
            layer_state = layer_probe.feed_state(feed)
            if not skip_evm:
                evm_state = evm_probe.feed_state(feed)
        screen_running = feed.session_name in screens
        alerts = evaluate_alerts(
            feed,
            screen_running=screen_running,
            log=log_summary,
            layer_state=layer_state,
            evm_state=evm_state,
            now=now,
            status_log_every_s=status_log_every_s,
        )

        item: dict[str, Any] = {
            "config": asdict(feed),
            "runtime": {
                "screen_running": screen_running,
                "screen_line": screens.get(feed.session_name),
            },
            "log": asdict(log_summary),
            "layer": layer_state,
            "evm": evm_state,
            "alerts": [asdict(alert) for alert in alerts],
        }
        if daily_reconcile:
            item["daily_reconciliation"] = summarize_daily(Path(feed.log_path), now - lookback_hours * 3600)
        feed_snapshots.append(item)

    aggregate = aggregate_snapshot(feed_snapshots, screens, screen_error)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "configs_dir": str(configs),
        "logs_dir": str(logs),
        "feed_count": len(feed_snapshots),
        "aggregate": aggregate,
        "feeds": feed_snapshots,
    }


def aggregate_snapshot(feed_snapshots: list[dict[str, Any]], screens: dict[str, str], screen_error: Optional[str]) -> dict[str, Any]:
    by_network: dict[str, dict[str, Any]] = {}
    severities = {"critical": 0, "warning": 0, "info": 0}
    for item in feed_snapshots:
        network = item["config"]["network"]
        bucket = by_network.setdefault(
            network,
            {"feed_count": 0, "running": 0, "critical": 0, "warning": 0, "stale_logs": 0},
        )
        bucket["feed_count"] += 1
        if item["runtime"]["screen_running"]:
            bucket["running"] += 1
        for alert in item["alerts"]:
            severity = alert["severity"]
            severities[severity] = severities.get(severity, 0) + 1
            if severity in ("critical", "warning"):
                bucket[severity] += 1
            if alert["code"] in ("log_stale", "status_stale"):
                bucket["stale_logs"] += 1

    unexpected_sessions = [
        name
        for name in sorted(screens)
        if not any(item["config"]["session_name"] == name for item in feed_snapshots)
    ]
    return {
        "by_network": by_network,
        "alert_counts": severities,
        "unexpected_relayer_sessions": unexpected_sessions,
        "screen_error": screen_error,
    }


def prometheus_text(snapshot: dict[str, Any]) -> str:
    lines = [
        "# HELP relayer_monitor_feed_expected Expected relayer feed from config inventory.",
        "# TYPE relayer_monitor_feed_expected gauge",
        "# HELP relayer_monitor_screen_running Whether the expected screen session is running.",
        "# TYPE relayer_monitor_screen_running gauge",
        "# HELP relayer_monitor_alerts Alerts by severity for each feed.",
        "# TYPE relayer_monitor_alerts gauge",
        "# HELP relayer_monitor_layer_report_age_seconds Latest Layer report age.",
        "# TYPE relayer_monitor_layer_report_age_seconds gauge",
        "# HELP relayer_monitor_evm_relay_age_seconds Latest EVM TellorDataBank relay age.",
        "# TYPE relayer_monitor_evm_relay_age_seconds gauge",
        "# HELP relayer_monitor_bridge_valset_lag_seconds Difference between Layer and EVM bridge validator timestamps.",
        "# TYPE relayer_monitor_bridge_valset_lag_seconds gauge",
    ]
    for item in snapshot["feeds"]:
        labels = f'network="{item["config"]["network"]}",feed="{item["config"]["feed"]}",mode="{item["config"]["mode"]}"'
        lines.append(f"relayer_monitor_feed_expected{{{labels}}} 1")
        lines.append(f"relayer_monitor_screen_running{{{labels}}} {1 if item['runtime']['screen_running'] else 0}")
        severity_counts: dict[str, int] = {}
        for alert in item["alerts"]:
            severity_counts[alert["severity"]] = severity_counts.get(alert["severity"], 0) + 1
        for severity in ("critical", "warning", "info"):
            lines.append(f'relayer_monitor_alerts{{{labels},severity="{severity}"}} {severity_counts.get(severity, 0)}')
        layer_age = ((item.get("layer") or {}).get("report_age_s"))
        if layer_age is not None:
            lines.append(f"relayer_monitor_layer_report_age_seconds{{{labels}}} {_to_float(layer_age)}")
        relay_age = (((item.get("evm") or {}).get("tellor_data_bank") or {}).get("relay_age_s"))
        if relay_age is not None:
            lines.append(f"relayer_monitor_evm_relay_age_seconds{{{labels}}} {_to_float(relay_age)}")
        layer_valset_ts = _to_int((item.get("layer") or {}).get("latest_validator_timestamp"))
        evm_valset_ts = _to_int((((item.get("evm") or {}).get("bridge") or {}).get("validator_timestamp")))
        if layer_valset_ts and evm_valset_ts:
            lines.append(f"relayer_monitor_bridge_valset_lag_seconds{{{labels}}} {max(0, layer_valset_ts - evm_valset_ts)}")
    return "\n".join(lines) + "\n"


def write_outputs(snapshot: dict[str, Any], json_output: Optional[str], prometheus_output: Optional[str]) -> str:
    rendered = json.dumps(snapshot, indent=2, sort_keys=True)
    if json_output:
        Path(json_output).write_text(rendered + "\n")
    if prometheus_output:
        Path(prometheus_output).write_text(prometheus_text(snapshot))
    return rendered
