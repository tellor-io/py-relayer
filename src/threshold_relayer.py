import time
import os
from eth_abi import decode
from src.relayer import (
    get_next_heartbeat_time, 
    handle_validator_set_update, 
    get_oracle_data_optimized,
    get_current_price_from_api,
    sleep
)
from src.backoff import poll_with_backoff
from src.cycle_list import CycleListCache
from src.evm_client import EVMClient
from src.layer_client import (
    get_layer_chain_status, 
    get_layer_chain_id, 
    get_attestation_data_before,
    get_validator_checkpoint_params,
    get_layer_latest_validator_timestamp,
    get_current_tip,
    get_oracle_module_params
)
from src.layer_tx_client import tip
from src.logger_utils import get_logger

logger = get_logger(__name__)

def _short_hex(s: str | None, *, keep: int = 8) -> str:
    """
    Shorten long hex strings for logging (avoid dumping full queryData).
    """
    if not s:
        return ""
    s = str(s)
    if len(s) <= (keep * 2 + 2):
        return s
    # Preserve 0x prefix if present
    if s.startswith("0x"):
        core = s[2:]
        return f"0x{core[:keep]}…{core[-keep:]}(len={len(core)})"
    return f"{s[:keep]}…{s[-keep:]}(len={len(s)})"

class ThresholdRelayer:
    """
    Threshold relayer implementing tip and relay logic with primary/backup modes
    """
    def __init__(self, mode: str = "primary"):
        self.mode = mode.lower()  # "primary" or "backup"
        self.next_heartbeat_time = 0
        self.layer_chain_id = ""
        self.heartbeat_interval = 0  # seconds - heartbeat interval
        self.offset = 0  # seconds - offset
        self.check_interval = 0  # seconds - main loop interval
        self.latest_api_price = {"price": None, "timestamp": 0} # latest price from API and last retrieval timestamp
        self._loop_count = 0
        self._last_status_log_ts = 0
        self._last_chain_issue_log_ts = 0
        # Keep INFO logs high-signal by default; allow tuning via env vars if desired.
        self._status_log_every_s = int(os.getenv("STATUS_LOG_EVERY", "300"))  # periodic status snapshot
        self._chain_issue_log_every_s = int(os.getenv("CHAIN_ISSUE_LOG_EVERY", "120"))  # rate-limit repeated chain warnings
        logger.info(f"Initialized {self.mode} threshold relayer")

    def _maybe_log_status(
        self,
        *,
        current_ts: int,
        query_id: str | None,
        query_data: str | None,
        latest_agg_report: dict | None,
        is_cycle_list: bool,
        should_tip: bool,
        tip_reason: str,
        should_relay: bool,
        relay_reason: str,
    ) -> None:
        """
        Periodic INFO status snapshot to help operators understand what the relayer is doing
        when it's not actively tipping/relaying.
        """
        if self._status_log_every_s <= 0:
            return
        if self._last_status_log_ts and (current_ts - self._last_status_log_ts) < self._status_log_every_s:
            return

        # Use "now" for age calculations so we don't show negative ages when e.g.
        # an API price was fetched later in the loop than `current_ts` was captured.
        now_ts = int(time.time())

        report_ts_ms = 0
        last_consensus_ts_ms = 0
        attestation_ts_ms = 0
        aggregate_power = None
        try:
            if latest_agg_report:
                report_ts_ms = int(latest_agg_report.get("timestamp", 0) or 0)
                last_consensus_ts_ms = int(latest_agg_report.get("last_consensus_timestamp", 0) or 0)
                attestation_ts_ms = int(latest_agg_report.get("attestation_timestamp", 0) or 0)
                aggregate_power = latest_agg_report.get("aggregate_power")
        except Exception:
            pass

        report_age_s = (now_ts - (report_ts_ms // 1000)) if report_ts_ms else None
        consensus_age_s = (now_ts - (last_consensus_ts_ms // 1000)) if last_consensus_ts_ms else None
        next_hb_in_s = int(self.next_heartbeat_time - now_ts) if self.next_heartbeat_time else None
        api_age_s = (
            int(time.time() - float(self.latest_api_price.get("timestamp") or 0))
            if self.latest_api_price.get("timestamp")
            else None
        )

        logger.info(
            "Status mode=%s query_id=%s query_data=%s cycle_list=%s report_age_s=%s consensus_age_s=%s next_heartbeat_in_s=%s "
            "api_price_age_s=%s should_tip=%s should_relay=%s",
            self.mode,
            _short_hex(query_id),
            _short_hex(query_data),
            is_cycle_list,
            report_age_s,
            consensus_age_s,
            next_hb_in_s,
            api_age_s,
            should_tip,
            should_relay,
        )
        logger.debug(
            "Status details report_ts_ms=%s attestation_ts_ms=%s aggregate_power=%s tip_reason=%s relay_reason=%s",
            report_ts_ms,
            attestation_ts_ms,
            aggregate_power,
            tip_reason,
            relay_reason,
        )

        self._last_status_log_ts = now_ts

    def start_relayer(self):
        """Start the threshold relayer process"""
        # load configuration
        query_id = os.getenv("QUERY_ID")
        query_data = os.getenv("QUERY_DATA")
        self.heartbeat_interval = int(os.getenv("SLEEP_TIME", "600"))  # heartbeat interval
        self.offset = int(os.getenv("OFFSET", "5"))
        price_threshold = float(os.getenv("PRICE_THRESHOLD", "0.01"))  # 1% default
        self.check_interval = int(os.getenv("CHECK_INTERVAL", "30"))  # main loop interval
        contract_type = "TellorDataBank"
        
        # oracle data optimization parameters
        optimistic_delay = int(os.getenv("OPTIMISTIC_DELAY", "900"))
        max_attestation_age = int(os.getenv("MAX_ATTESTATION_AGE", "600"))
        max_data_age = int(os.getenv("MAX_DATA_AGE", "14400"))
        min_stake_percentage = int(os.getenv("MIN_STAKE_PERCENTAGE", "33"))

        if self.mode == "backup":
            price_threshold = price_threshold * 2
            self.heartbeat_interval = int(self.heartbeat_interval * 1.25)
        
        logger.info(
            "Starting threshold relayer mode=%s query_id=%s query_data=%s contract_type=%s",
            self.mode,
            _short_hex(query_id),
            _short_hex(query_data),
            contract_type,
        )
        logger.info(
            "Config heartbeat_interval_s=%s offset_s=%s check_interval_s=%s price_threshold_pct=%.4f "
            "optimistic_delay_s=%s max_attestation_age_s=%s max_data_age_s=%s min_stake_pct=%s",
            self.heartbeat_interval,
            self.offset,
            self.check_interval,
            price_threshold * 100,
            optimistic_delay,
            max_attestation_age,
            max_data_age,
            min_stake_percentage,
        )

        # initialize EVM client
        evm = EVMClient()
        evm.init_web3()
        evm.setup_data_bridge_contract()
        evm.setup_tellor_data_bank_contract()
        logger.info("EVM contracts ready (data bridge + TellorDataBank)")

        # get layer chain ID
        self.layer_chain_id, e = get_layer_chain_id()
        if e:
            logger.error(f"Error getting layer chain ID: {e}")
            return
        logger.info(f"Layer chain id: {self.layer_chain_id}")

        # initialize heartbeat
        self.next_heartbeat_time = get_next_heartbeat_time(self.heartbeat_interval, self.offset)
        logger.info(f"Next heartbeat time (unix): {self.next_heartbeat_time}")
        should_tip = False
        should_relay = False
        tip_reason = ""
        relay_reason = ""
        cycle_list_cache = CycleListCache()

        # main loop
        while True:
            try:
                self._loop_count += 1
                # capture time + latest agg once per loop
                current_ts = int(time.time())
                logger.debug(
                    "Loop tick=%s now=%s next_heartbeat=%s",
                    self._loop_count,
                    current_ts,
                    self.next_heartbeat_time,
                )

                # check layer chain status
                chain_status, error = get_layer_chain_status()
                if chain_status or error:
                    # Avoid flooding logs if the chain is down/catching up; log at most every CHAIN_ISSUE_LOG_EVERY seconds.
                    if (not self._last_chain_issue_log_ts) or (
                        current_ts - self._last_chain_issue_log_ts >= self._chain_issue_log_every_s
                    ):
                        logger.warning(f"Layer chain status issue: {chain_status} {error or ''}".strip())
                        self._last_chain_issue_log_ts = current_ts
                    sleep(self.check_interval)
                    continue

                latest_agg_report, e = self.get_latest_agg_report(query_id)
                if e:
                    logger.error(f"Error getting latest aggregate report: {e}")
                    latest_agg_report = dict()
                else:
                    try:
                        latest_report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000
                        logger.debug(
                            "Latest Layer aggregate ts_s=%s age_s=%s last_consensus_ts_s=%s",
                            latest_report_ts,
                            (current_ts - latest_report_ts) if latest_report_ts else None,
                            int(latest_agg_report.get("last_consensus_timestamp", 0)) // 1000,
                        )
                    except Exception:
                        pass

                query_data_env = os.getenv("QUERY_DATA") or ""
                is_cycle_list = False
                if query_data_env:
                    try:
                        is_cycle_list = cycle_list_cache.contains_query_data(query_data_env)
                    except Exception as _:
                        # Best-effort: don't fail the relayer if cycle list fetch/parsing has issues.
                        is_cycle_list = False

                # handle validator set updates
                e = handle_validator_set_update(evm)
                if e:
                    logger.error(f"Error handling validator set update: {e}")
                    sleep(self.check_interval)
                    continue

                # determine if we should tip
                should_tip, tip_reason = self.determine_should_tip(
                    current_ts, latest_agg_report, query_id, price_threshold, evm, is_cycle_list
                )
                logger.debug("Tip decision should_tip=%s reason=%s", should_tip, tip_reason)
                if should_tip:
                    logger.info(
                        "Action tip mode=%s query_id=%s query_data=%s reason=%s",
                        self.mode,
                        _short_hex(query_id),
                        _short_hex(query_data),
                        tip_reason,
                    )
                    self.tip_and_wait(query_data, current_ts)
                    latest_agg_report, e = self.get_latest_agg_report(query_id)
                    if e:
                        logger.error(f"Error getting latest aggregate report: {e}")
                        latest_agg_report = dict()

                # determine if we should relay
                should_relay, relay_reason = self.determine_should_relay(
                    current_ts, latest_agg_report, query_id, price_threshold, evm, is_cycle_list
                )
                logger.debug("Relay decision should_relay=%s reason=%s", should_relay, relay_reason)
                if should_relay:
                    logger.info(
                        "Action relay mode=%s query_id=%s contract_type=%s reason=%s",
                        self.mode,
                        _short_hex(query_id),
                        contract_type,
                        relay_reason,
                    )
                    self.relay_data(
                        evm, query_id, contract_type, optimistic_delay, 
                        max_attestation_age, max_data_age, min_stake_percentage
                    )

                # periodic operator-friendly status snapshot (even when idle)
                self._maybe_log_status(
                    current_ts=current_ts,
                    query_id=query_id,
                    query_data=query_data,
                    latest_agg_report=latest_agg_report,
                    is_cycle_list=is_cycle_list,
                    should_tip=should_tip,
                    tip_reason=tip_reason,
                    should_relay=should_relay,
                    relay_reason=relay_reason,
                )

            except Exception as e:
                logger.exception(f"Unexpected error in main loop: {e}")

            # sleep for check interval
            # if tipped for price threshold change on this round, only sleep for 20 seconds
            # if should_tip and tip_reason string contains "threshold tip"
            price_threshold_check_interval = 20
            if should_tip and "threshold tip" in tip_reason and price_threshold_check_interval < self.check_interval:
                sleep(price_threshold_check_interval)
            else:
                sleep(self.check_interval)

    def get_latest_agg_report(self, query_id: str) -> tuple[dict, Exception]:
        """Get the latest aggregate report from Layer"""
        try:
            current_time_ms = int(time.time()) * 1000
            attestation_data, e = get_attestation_data_before(query_id, current_time_ms)
            if e:
                return None, e
            
            return attestation_data, None
        except Exception as e:
            return None, Exception(f"Failed to get latest aggregate report: {e}")

    def determine_should_tip(self, current_ts: int, latest_agg_report: dict, 
                           query_id: str, price_threshold: float, evm: EVMClient, is_cycle_list: bool) -> tuple[bool, str]:
        """Determine if we should tip based on heartbeat or threshold logic"""
        
        if self.mode == "backup":
            return self._determine_should_tip_backup(current_ts, latest_agg_report, query_id, price_threshold, evm, is_cycle_list)
        else:
            return self._determine_should_tip_primary(current_ts, latest_agg_report, query_id, price_threshold, evm, is_cycle_list)

    def _determine_should_tip_backup(self, current_ts: int, latest_agg_report: dict, 
                                   query_id: str, price_threshold: float, evm: EVMClient, is_cycle_list: bool) -> tuple[bool, str]:
        """Backup relayer tipping logic per pseudocode"""
        
        # check whether should tip:
        # if current_tip > 600 or current_time - last_aggregate_report.timestamp < heartbeat_interval/5)
        #     return false
        current_tip_amount, error = self.get_current_tip_amount()
        if error:
            logger.error(f"Error getting current tip amount: {error}")
            return False, f"error getting current tip amount: {error}"
        latest_report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000  # convert ms to seconds
        # initial tip checks - skip if tip already exists (recent) or reporter just not reporting for tips (older)
        # also skip if we already have a recent aggregate report
        if current_tip_amount > 600 or (current_ts - latest_report_ts < self.heartbeat_interval // 5):
            return False, f"skip - current tip amount: {current_tip_amount}, latest report age: {current_ts - latest_report_ts}s, threshold: {self.heartbeat_interval // 5}s"
        
        # heartbeat:
        # If (current_time - last_aggregate_report.timestamp > heartbeat_interval) 
        #     return true # should tip
        if (not is_cycle_list) and (current_ts - latest_report_ts > self.heartbeat_interval):
            return True, f"heartbeat tip - report age: {current_ts - latest_report_ts}s > {self.heartbeat_interval}s"
        
        # threshold
        # do consensus check, same as primary relayer
        last_consensus_ts = int(latest_agg_report.get("last_consensus_timestamp", 0)) // 1000  # convert ms to seconds
        consensus_condition = (
            latest_report_ts == last_consensus_ts or
            current_ts - last_consensus_ts < int(self.heartbeat_interval * 1.5)
        )
        
        if not consensus_condition:
            return False, "no consensus for threshold tip"
        
        # if price_change > threshold: return True
        if current_ts - latest_report_ts > 30:  # basic staleness check
            try:
                latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
                if error or latest_relayed_data is None:
                    logger.debug("No previous relay data found for threshold comparison")
                    return False, "no previous relay data"
                
                real_price, error = self.get_price_from_api()
                if error:
                    logger.error(f"Failed to get current price: {error}")
                    return False, "failed to get current price"
                
                price_change_pct = self.get_price_change_percentage(latest_relayed_data, real_price)
                if price_change_pct >= price_threshold:
                    try:
                        evm_last_price = float(latest_relayed_data["value"][0])
                    except Exception:
                        evm_last_price = 0.0
                    skip, reason = self._should_skip_threshold_tip_due_to_recent_layer(
                        current_ts, latest_agg_report, evm_last_price, real_price, price_threshold
                    )
                    if skip:
                        return False, f"skip threshold tip - {reason}"
                    return True, f"threshold tip - price change: {price_change_pct*100:.2f}% >= {price_threshold*100:.2f}%"
                    
            except Exception as e:
                logger.error(f"Error in backup threshold tip logic: {e}")
        
        return False, "no tip needed"

    def _determine_should_tip_primary(self, current_ts: int, latest_agg_report: dict, 
                                    query_id: str, price_threshold: float, evm: EVMClient, is_cycle_list: bool) -> tuple[bool, str]:
        """Primary relayer tipping logic (original logic)"""
        
        # heartbeat tip (preferred)
        next_heartbeat_time = self.next_heartbeat_time
        latest_report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000  # convert ms to seconds
        if not is_cycle_list:
            if current_ts > next_heartbeat_time:
                self.next_heartbeat_time = get_next_heartbeat_time(self.heartbeat_interval, int(os.getenv("OFFSET", "5")))
                logger.info(f"Updated next heartbeat time: {self.next_heartbeat_time}")
                if latest_report_ts < next_heartbeat_time:
                    if next_heartbeat_time - latest_report_ts > self.check_interval:
                        return True, f"heartbeat tip - current: {current_ts}, heartbeat: {next_heartbeat_time}, report age: {current_ts - latest_report_ts}s"
            
        
        # threshold tip (only if no heartbeat tip)
        current_tip_amount, error = self.get_current_tip_amount()
        if error:
            logger.error(f"Error getting current tip amount: {error}")
            return False, f"error getting current tip amount: {error}"
        last_consensus_ts = int(latest_agg_report.get("last_consensus_timestamp", 0)) // 1000  # convert ms to seconds
        # only consider threshold tipping if we're generally getting consensus data
        consensus_condition = (
            latest_report_ts == last_consensus_ts or
            current_ts - last_consensus_ts < int(self.heartbeat_interval * 1.5)
        )
        if current_tip_amount == 0 and consensus_condition:
            if current_ts - latest_report_ts > 30:  # 30 seconds threshold
                # first check whether latest aggregate report is older than heartbeat_interval seconds old
                # this should only happen when relayer first starts, and latest report is older than heartbeat interval
                if current_ts - latest_report_ts > int(self.heartbeat_interval + self.check_interval):
                    return True, f"heartbeat tip catch-up - current: {current_ts}, latest_aggregate_report_ts: {latest_report_ts}, report age: {current_ts - latest_report_ts}s"
                try:
                    latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
                    if error or latest_relayed_data is None:
                        logger.debug("No previous relay data found for threshold comparison")
                        return False, "no previous relay data"
                    
                    real_price, error = self.get_price_from_api()
                    if error:
                        logger.error(f"Failed to get current price: {error}")
                        return False, "failed to get current price"
                    
                    price_change_pct = self.get_price_change_percentage(latest_relayed_data, real_price)
                    if price_change_pct >= price_threshold:
                        try:
                            evm_last_price = float(latest_relayed_data["value"][0])
                        except Exception:
                            evm_last_price = 0.0
                        skip, reason = self._should_skip_threshold_tip_due_to_recent_layer(
                            current_ts, latest_agg_report, evm_last_price, real_price, price_threshold
                        )
                        if skip:
                            return False, f"skip threshold tip - {reason}"
                        return True, f"threshold tip - price change: {price_change_pct*100:.2f}% >= {price_threshold*100:.2f}%"
                        
                except Exception as e:
                    logger.error(f"Error in threshold tip logic: {e}")
        
        return False, "no tip needed"

    def determine_should_relay(self, current_ts: int, latest_agg_report: dict, 
                             query_id: str, price_threshold: float, evm: EVMClient, is_cycle_list: bool) -> tuple[bool, str]:
        """Determine if we should relay based on heartbeat or threshold logic"""
        
        if self.mode == "backup":
            return self._determine_should_relay_backup(current_ts, latest_agg_report, query_id, price_threshold, evm, is_cycle_list)
        else:
            return self._determine_should_relay_primary(current_ts, latest_agg_report, query_id, price_threshold, evm, is_cycle_list)

    def _determine_should_relay_backup(self, current_ts: int, latest_agg_report: dict, 
                                     query_id: str, price_threshold: float, evm: EVMClient, is_cycle_list: bool) -> tuple[bool, str]:
        """Backup relayer relay logic per pseudocode"""
        
        try:
            latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
            if error:
                logger.error(f"Error getting last relayed data: {error}")
                return False, "backup error getting last relayed data"
            
            if latest_relayed_data is None:
                return True, "backup no previous relay data - initial relay"

            if is_cycle_list:
                try:
                    layer_ts_ms = int(latest_agg_report.get("timestamp", 0))
                    last_relayed_ts_ms = int(float(latest_relayed_data.get("timestamp", 0)) * 1000)
                    if layer_ts_ms > last_relayed_ts_ms:
                        return True, "backup cycle list relay - newer Layer aggregate available"
                except Exception:
                    pass
            
            relay_timestamp = latest_relayed_data.get("relay_timestamp", 0)
            
            # check whether should relay:
            # if current_time - last_relayed_data.relayTimestamp > heartbeat_interval:
            #     return True # should relay
            if current_ts - relay_timestamp > self.heartbeat_interval:
                return True, f"backup heartbeat relay - relay age: {current_ts - relay_timestamp}s > {self.heartbeat_interval}s"
            
            # else if consensus_check
            last_consensus_ts = int(latest_agg_report.get("last_consensus_timestamp", 0)) // 1000  # convert ms to seconds
            latest_report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000  # convert ms to seconds
            consensus_condition = (
                latest_report_ts == last_consensus_ts or
                current_ts - last_consensus_ts < int(self.heartbeat_interval * 1.5)
            )
            
            if consensus_condition:
                # if price_change_pct > threshold return True
                real_price, error = self.get_price_from_api()
                if error:
                    logger.error(f"Failed to get current price for backup threshold relay: {error}")
                    return False, "backup failed to get current price"
                
                price_change_pct = self.get_price_change_percentage(latest_relayed_data, real_price)
                if price_change_pct >= price_threshold:
                    return True, f"backup threshold relay - price change: {price_change_pct*100:.2f}% >= {price_threshold*100:.2f}%"
        
        except Exception as e:
            logger.error(f"Error in backup relay determination logic: {e}")
        
        return False, "backup no relay needed"

    def _determine_should_relay_primary(self, current_ts: int, latest_agg_report: dict, 
                                      query_id: str, price_threshold: float, evm: EVMClient, is_cycle_list: bool) -> tuple[bool, str]:
        """Primary relayer relay logic (original logic)"""
        
        try:
            latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
            if error:
                logger.error(f"Error getting last relayed data: {error}")
                return False, "error getting last relayed data"
            
            if latest_relayed_data is None:
                return True, "no previous relay data - initial relay"

            if is_cycle_list:
                try:
                    layer_ts_ms = int(latest_agg_report.get("timestamp", 0))
                    last_relayed_ts_ms = int(float(latest_relayed_data.get("timestamp", 0)) * 1000)
                    if layer_ts_ms > last_relayed_ts_ms:
                        return True, "cycle list relay - newer Layer aggregate available"
                except Exception:
                    pass
            
            last_heartbeat_ts = self.get_heartbeat_ts_before(current_ts, self.heartbeat_interval)
            relay_timestamp = latest_relayed_data.get("relay_timestamp", 0)
            
            # heartbeat relay
            if relay_timestamp < last_heartbeat_ts - self.check_interval:
                return True, f"heartbeat relay - last relay: {relay_timestamp}, last heartbeat: {last_heartbeat_ts}"
            
            # threshold relay (consensus-gated / recent-consensus-gated)
            last_consensus_ts = int(latest_agg_report.get("last_consensus_timestamp", 0)) // 1000  # convert ms to seconds
            latest_report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000  # convert ms to seconds
            consensus_condition = (
                latest_report_ts == last_consensus_ts or
                current_ts - last_consensus_ts < int(self.heartbeat_interval * 1.5)
            )
            if consensus_condition:
                real_price, error = self.get_price_from_api()
                if error:
                    logger.error(f"Failed to get current price for threshold relay: {error}")
                    return False, "failed to get current price"
                
                price_change_pct = self.get_price_change_percentage(latest_relayed_data, real_price)
                if price_change_pct >= price_threshold:
                    return True, f"threshold relay - price change: {price_change_pct*100:.2f}% >= {price_threshold*100:.2f}%"
        
        except Exception as e:
            logger.error(f"Error in relay determination logic: {e}")
        
        return False, "no relay needed"

    def get_current_tip_amount(self) -> tuple[int, Exception]:
        """
        Get current tip amount for the query data from Layer chain
        Returns 0 if no tip or error
        """
        try:
            query_data = os.getenv("QUERY_DATA")
            if not query_data:
                logger.error("QUERY_DATA not set in environment")
                return 0, Exception("QUERY_DATA not set in environment")
            
            tip_data, error = get_current_tip(query_data)
            if error:
                logger.debug(f"No current tip found or error getting tip: {error}")
                return 0, Exception("No current tip found or error getting tip")
            
            if tip_data and "amount" in tip_data:
                tip_amount = int(tip_data["amount"])
                logger.debug(f"Current tip amount for query: {tip_amount}")
                return tip_amount, None
            
            return 0, None
        except Exception as e:
            logger.error(f"Error getting current tip amount: {e}")
            return 0, Exception(f"Error getting current tip amount: {e}")

    def get_price_change_percentage(self, latest_relayed_data: dict, real_price: float) -> float:
        """Calculate price change percentage"""
        try:
            last_price = latest_relayed_data["value"][0]  # assuming price is in value[0]
            if last_price == 0:
                return float('inf')  # infinite change if last price was 0
            return abs(real_price - last_price) / last_price
        except Exception as e:
            logger.error(f"Error calculating price change: {e}")
            return 0.0

    def _decode_layer_aggregate_price(self, latest_agg_report: dict) -> float | None:
        """
        Decode SpotPrice aggregate_value to a float.
        Assumes uint256 scaled by 1e18 (consistent with existing Layer fallback logic).
        """
        try:
            value_hex = latest_agg_report.get("aggregate_value") or latest_agg_report.get("aggregateValue")
            if not value_hex:
                return None
            value_bytes = bytes.fromhex(str(value_hex))
            value_decoded = decode(["uint256"], value_bytes)
            return float(value_decoded[0]) / 10**18
        except Exception:
            return None

    def _should_skip_threshold_tip_due_to_recent_layer(
        self,
        current_ts: int,
        latest_agg_report: dict,
        evm_last_price: float,
        real_price: float,
        price_threshold: float,
    ) -> tuple[bool, str]:
        """
        If Layer has a recent report that already reflects the real price closely enough
        (and in the correct direction relative to last relayed EVM price), skip tipping.
        """
        try:
            max_age = int(os.getenv("LAYER_RECENT_REPORT_MAX_AGE", "60"))
            latest_report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000
            if latest_report_ts == 0 or (current_ts - latest_report_ts) > max_age:
                return False, "layer report not recent enough"

            layer_price = self._decode_layer_aggregate_price(latest_agg_report)
            if layer_price is None or layer_price <= 0:
                return False, "could not decode layer price"

            # closeness check vs real price
            layer_vs_real_pct = abs(real_price - layer_price) / layer_price
            if layer_vs_real_pct > (price_threshold / 2):
                return False, f"layer price not close enough to real ({layer_vs_real_pct:.6f} > {price_threshold/2:.6f})"

            # direction check relative to last relayed EVM price
            if real_price > evm_last_price and not (layer_price > evm_last_price):
                return False, "direction mismatch (real>evm_last but layer<=evm_last)"
            if real_price < evm_last_price and not (layer_price < evm_last_price):
                return False, "direction mismatch (real<evm_last but layer>=evm_last)"

            return True, f"layer recent+close+direction-ok (layer_vs_real={layer_vs_real_pct*100:.3f}%)"
        except Exception as e:
            return False, f"layer gating error: {e}"

    def get_heartbeat_ts_before(self, current_ts: int, sleep_time: int) -> int:
        """Get the heartbeat timestamp before the current time"""
        offset = int(os.getenv("OFFSET", "5"))
        basis_time = 1735689600 + offset  # 1/1/2025 00:00:00 GMT + offset
        
        # calculate how many intervals have passed
        diff = current_ts - basis_time
        intervals_passed = int(diff / sleep_time)
        
        # return the timestamp of the most recent heartbeat
        return basis_time + (intervals_passed * sleep_time)

    def get_layer_validator_checkpoint_params(self) -> dict:
        """Get Layer validator checkpoint parameters"""
        try:
            latest_timestamp, e = get_layer_latest_validator_timestamp()
            if e:
                logger.error(f"Error getting latest validator timestamp: {e}")
                return None
            
            checkpoint_params, e = get_validator_checkpoint_params(latest_timestamp)
            if e:
                logger.error(f"Error getting validator checkpoint params: {e}")
                return None
            
            return checkpoint_params
        except Exception as e:
            logger.error(f"Error getting layer validator checkpoint params: {e}")
            return None

    def tip_and_wait(self, query_data: str, ts_before_tip: int):
        """Tip and wait for new data"""
        max_wait_time = float(os.getenv("TIP_WAIT_TIMEOUT", "30"))
        
        try:
            # submit tip
            logger.debug(
                "Submitting Layer tip query_data=%s creator=%s rpc=%s chain_id=%s",
                _short_hex(query_data),
                os.getenv("LAYER_TX_CREATOR_ADDRESS"),
                os.getenv("LAYER_RPC_ENDPOINT"),
                self.layer_chain_id,
            )
            tip(query_data, os.getenv("LAYER_TX_CREATOR_ADDRESS"), 
                os.getenv("LAYER_RPC_ENDPOINT"), self.layer_chain_id)
            
            logger.info("Tip submitted, waiting for new Layer aggregate...")
            fast_attempts = int(os.getenv("TIP_FAST_ATTEMPTS", "8"))
            fast_sleep = float(os.getenv("TIP_FAST_SLEEP", "0.5"))
            max_sleep = float(os.getenv("TIP_MAX_SLEEP", "5"))
            logger.debug(
                "Tip wait config timeout_s=%s fast_attempts=%s fast_sleep_s=%s max_sleep_s=%s",
                max_wait_time,
                fast_attempts,
                fast_sleep,
                max_sleep,
            )

            def _has_new_report():
                query_id = os.getenv("QUERY_ID")
                latest_agg_report, e = self.get_latest_agg_report(query_id)
                if e is not None or not latest_agg_report:
                    return None
                report_ts = int(latest_agg_report.get("timestamp", 0))
                if report_ts > (ts_before_tip * 1000):
                    return report_ts
                return None

            try:
                report_ts = poll_with_backoff(
                    _has_new_report,
                    fast_attempts=fast_attempts,
                    fast_sleep=fast_sleep,
                    max_sleep=max_sleep,
                    timeout=max_wait_time,
                    description="new Layer aggregate after tip",
                )
                delta_s = (int(report_ts) // 1000) - int(ts_before_tip) if report_ts else None
                logger.info(f"New data received after tip - report_ts_ms={report_ts} delta_s={delta_s}")
            except TimeoutError:
                logger.info(f"Max wait time ({max_wait_time}s) reached, continuing...")
                
        except Exception as e:
            logger.exception(f"Error in tip_and_wait: {e}")

    def relay_data(self, evm: EVMClient, query_id: str, contract_type: str, 
                  optimistic_delay: int, max_attestation_age: int, max_data_age: int, 
                  min_stake_percentage: int):
        """Relay oracle data to EVM chain"""
        try:
            user_data = {"user_trigger_timestamp": int(time.time())}
            
            # get last relayed timestamp for optimized data retrieval
            last_relayed_data, error = evm.get_last_relayed_data(contract_type)
            last_relayed_timestamp = 0
            if error is None and last_relayed_data:
                last_relayed_timestamp = int(float(last_relayed_data["timestamp"]) * 1000)
            logger.debug("Last relayed timestamp_ms=%s", last_relayed_timestamp)

            # get optimized oracle data
            logger.debug(
                "Fetching oracle data optimized query_id=%s optimistic_delay_s=%s max_attestation_age_s=%s max_data_age_s=%s min_stake_pct=%s",
                _short_hex(query_id),
                optimistic_delay,
                max_attestation_age,
                max_data_age,
                min_stake_percentage,
            )
            oracle_data, error = get_oracle_data_optimized(
                query_id, optimistic_delay, max_attestation_age, 
                max_data_age, min_stake_percentage, last_relayed_timestamp
            )
            
            if error:
                # Common, non-fatal: "Add a tip." / "Relay after optimistic timestamp" / "Insufficient attestation power"
                logger.warning(f"Oracle data not relayed: {error}")
                return

            # Helpful summary of what we're about to relay (INFO-level, once per relay)
            try:
                report = oracle_data.get("oracle_attestation_data", {}).get("report", {})
                report_ts_ms = int(report.get("timestamp", 0) or 0)
                att_ts_ms = int(oracle_data.get("oracle_attestation_data", {}).get("attestationTimestamp", 0) or 0)
                power = report.get("aggregatePower")
                last_consensus_ms = report.get("lastConsensusTimestamp")
                now_ms = int(time.time() * 1000)
                logger.info(
                    "Relaying Layer report query_id=%s report_ts_ms=%s attestation_ts_ms=%s age_s=%.1f power=%s last_consensus_ms=%s",
                    _short_hex(query_id),
                    report_ts_ms,
                    att_ts_ms,
                    (now_ms - report_ts_ms) / 1000.0 if report_ts_ms else -1,
                    power,
                    last_consensus_ms,
                )
            except Exception:
                logger.debug("Could not summarize oracle_data for logging", exc_info=True)
            
            # submit to EVM
            tx_hash, error = evm.update_oracle_data(oracle_data, contract_type, user_data)
            if error:
                logger.error(f"Error updating oracle data: {error}")
                return
            
            logger.info(f"Oracle data relay successful - tx: {tx_hash.hex()}")
            
        except Exception as e:
            logger.exception(f"Error in relay_data: {e}")

    def get_price_from_api(self) -> tuple[float, Exception]:
        """Get the current price from the API"""
        current_time = time.time()
        if current_time - self.latest_api_price["timestamp"] > 10:
            latest_price, error = get_current_price_from_api()
            if error:
                logger.error(f"Error getting current price from API: {error}")
                return None, error
            self.latest_api_price = {"price": latest_price, "timestamp": current_time}
        return self.latest_api_price["price"], None

def start_primary_threshold_relayer():
    """Entry point for the primary threshold relayer"""
    relayer = ThresholdRelayer(mode="primary")
    relayer.start_relayer()

def start_backup_threshold_relayer():
    """Entry point for the backup threshold relayer"""
    relayer = ThresholdRelayer(mode="backup")
    relayer.start_relayer()