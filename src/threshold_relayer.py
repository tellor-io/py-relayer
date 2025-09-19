import time
import os
from src.relayer import (
    get_next_heartbeat_time, 
    handle_validator_set_update, 
    get_oracle_data_optimized,
    get_current_price_from_api,
    sleep
)
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
        logger.info(f"Initialized {self.mode} threshold relayer")

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
        
        logger.info(f"Starting improved threshold relayer for query ID {query_id}")
        logger.info(f"Heartbeat interval: {self.heartbeat_interval} seconds")
        logger.info(f"Price threshold: {price_threshold * 100}%")
        logger.info(f"Check interval: {self.check_interval} seconds")

        # initialize EVM client
        evm = EVMClient()
        evm.init_web3()
        evm.setup_data_bridge_contract()
        evm.setup_tellor_data_bank_contract()

        # get layer chain ID
        self.layer_chain_id, e = get_layer_chain_id()
        if e:
            logger.error(f"Error getting layer chain ID: {e}")
            return

        # initialize heartbeat
        self.next_heartbeat_time = get_next_heartbeat_time(self.heartbeat_interval, self.offset)
        logger.info(f"Next heartbeat time: {self.next_heartbeat_time}")
        should_tip = False
        should_relay = False
        tip_reason = ""
        relay_reason = ""

        # main loop
        while True:
            try:
                # capture time + latest agg once per loop
                current_ts = int(time.time())

                # check layer chain status
                chain_status, error = get_layer_chain_status()
                if chain_status or error:
                    logger.warning(f"Layer chain status issue: {chain_status} or {error}")
                    sleep(self.check_interval)
                    continue

                latest_agg_report, e = self.get_latest_agg_report(query_id)
                if e:
                    logger.error(f"Error getting latest aggregate report: {e}")
                    latest_agg_report = dict()

                # handle validator set updates
                e = handle_validator_set_update(evm)
                if e:
                    logger.error(f"Error handling validator set update: {e}")
                    sleep(self.check_interval)
                    continue

                # determine if we should tip
                should_tip, tip_reason = self.determine_should_tip(
                    current_ts, latest_agg_report, query_id, price_threshold, evm
                )
                if should_tip:
                    logger.info(f"Tipping: {tip_reason}")
                    self.tip_and_wait(query_data, current_ts)
                    latest_agg_report, e = self.get_latest_agg_report(query_id)
                    if e:
                        logger.error(f"Error getting latest aggregate report: {e}")
                        latest_agg_report = dict()

                # determine if we should relay
                should_relay, relay_reason = self.determine_should_relay(
                    current_ts, latest_agg_report, query_id, price_threshold, evm
                )
                if should_relay:
                    logger.info(f"Relaying: {relay_reason}")
                    self.relay_data(
                        evm, query_id, contract_type, optimistic_delay, 
                        max_attestation_age, max_data_age, min_stake_percentage
                    )

            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")

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
                           query_id: str, price_threshold: float, evm: EVMClient) -> tuple[bool, str]:
        """Determine if we should tip based on heartbeat or threshold logic"""
        
        if self.mode == "backup":
            return self._determine_should_tip_backup(current_ts, latest_agg_report, query_id, price_threshold, evm)
        else:
            return self._determine_should_tip_primary(current_ts, latest_agg_report, query_id, price_threshold, evm)

    def _determine_should_tip_backup(self, current_ts: int, latest_agg_report: dict, 
                                   query_id: str, price_threshold: float, evm: EVMClient) -> tuple[bool, str]:
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
        if current_ts - latest_report_ts > self.heartbeat_interval:
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
                    return True, f"threshold tip - price change: {price_change_pct*100:.2f}% >= {price_threshold*100:.2f}%"
                    
            except Exception as e:
                logger.error(f"Error in backup threshold tip logic: {e}")
        
        return False, "no tip needed"

    def _determine_should_tip_primary(self, current_ts: int, latest_agg_report: dict, 
                                    query_id: str, price_threshold: float, evm: EVMClient) -> tuple[bool, str]:
        """Primary relayer tipping logic (original logic)"""
        
        # heartbeat tip (preferred)
        next_heartbeat_time = self.next_heartbeat_time
        latest_report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000  # convert ms to seconds
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
                        return True, f"threshold tip - price change: {price_change_pct*100:.2f}% >= {price_threshold*100:.2f}%"
                        
                except Exception as e:
                    logger.error(f"Error in threshold tip logic: {e}")
        
        return False, "no tip needed"

    def determine_should_relay(self, current_ts: int, latest_agg_report: dict, 
                             query_id: str, price_threshold: float, evm: EVMClient) -> tuple[bool, str]:
        """Determine if we should relay based on heartbeat or threshold logic"""
        
        if self.mode == "backup":
            return self._determine_should_relay_backup(current_ts, latest_agg_report, query_id, price_threshold, evm)
        else:
            return self._determine_should_relay_primary(current_ts, latest_agg_report, query_id, price_threshold, evm)

    def _determine_should_relay_backup(self, current_ts: int, latest_agg_report: dict, 
                                     query_id: str, price_threshold: float, evm: EVMClient) -> tuple[bool, str]:
        """Backup relayer relay logic per pseudocode"""
        
        try:
            latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
            if error:
                logger.error(f"Error getting last relayed data: {error}")
                return False, "backup error getting last relayed data"
            
            if latest_relayed_data is None:
                return True, "backup no previous relay data - initial relay"
            
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
                                      query_id: str, price_threshold: float, evm: EVMClient) -> tuple[bool, str]:
        """Primary relayer relay logic (original logic)"""
        
        try:
            latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
            if error:
                logger.error(f"Error getting last relayed data: {error}")
                return False, "error getting last relayed data"
            
            if latest_relayed_data is None:
                return True, "no previous relay data - initial relay"
            
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
        max_wait_time = 30  # seconds
        
        try:
            # submit tip
            tip(query_data, os.getenv("LAYER_ADDRESS"), 
                os.getenv("LAYER_RPC_ENDPOINT"), self.layer_chain_id)
            
            logger.info("Tip submitted, waiting for new data...")
            sleep(3)  # initial wait
            
            # wait for new data or timeout
            start_wait = int(time.time())
            while True:
                current_time = int(time.time())
                if current_time - start_wait > max_wait_time:
                    logger.info(f"Max wait time ({max_wait_time}s) reached, continuing...")
                    break
                
                # check if we have new data
                try:
                    query_id = os.getenv("QUERY_ID")
                    latest_agg_report, e = self.get_latest_agg_report(query_id)
                    if e is None and latest_agg_report:
                        report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000
                        if report_ts > ts_before_tip:
                            logger.info(f"New data received after tip - report timestamp: {report_ts}")
                            break
                except Exception as e:
                    logger.debug(f"Error checking for new data: {e}")
                
                sleep(0.5)  # short sleep before checking again
                
        except Exception as e:
            logger.error(f"Error in tip_and_wait: {e}")

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

            # get optimized oracle data
            oracle_data, error = get_oracle_data_optimized(
                query_id, optimistic_delay, max_attestation_age, 
                max_data_age, min_stake_percentage, last_relayed_timestamp
            )
            
            if error:
                logger.error(f"Error getting oracle data: {error}")
                return
            
            # submit to EVM
            tx_hash, error = evm.update_oracle_data(oracle_data, contract_type, user_data)
            if error:
                logger.error(f"Error updating oracle data: {error}")
                return
            
            logger.info(f"Oracle data relay successful - tx: {tx_hash.hex()}")
            
        except Exception as e:
            logger.error(f"Error in relay_data: {e}")

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