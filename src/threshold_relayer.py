import time
import os
import requests
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
    get_current_aggregate_report,
    get_attestation_data_before,
    get_current_power_threshold,
    get_validator_checkpoint_params,
    get_layer_latest_validator_timestamp,
    get_current_tip
)
from src.layer_tx_client import tip
from src.logger_utils import get_logger

logger = get_logger(__name__)

class ImprovedThresholdRelayer:
    """
    Improved threshold relayer implementing the new tip and relay logic
    """
    def __init__(self):
        self.next_heartbeat_time = 0
        self.layer_chain_id = ""
        self.check_time = 30  # seconds - how far back to check for stale data

    def start_relayer(self):
        """Start the improved threshold relayer process"""
        # load configuration
        query_id = os.getenv("QUERY_ID")
        query_data = os.getenv("QUERY_DATA")
        sleep_time = int(os.getenv("SLEEP_TIME", "600"))  # heartbeat interval
        price_threshold = float(os.getenv("PRICE_THRESHOLD", "0.01"))  # 1% default
        check_interval = int(os.getenv("CHECK_INTERVAL", "30"))  # main loop interval
        contract_type = "TellorDataBank"
        
        # oracle data optimization parameters
        optimistic_delay = int(os.getenv("OPTIMISTIC_DELAY", "900"))
        max_attestation_age = int(os.getenv("MAX_ATTESTATION_AGE", "600"))
        max_data_age = int(os.getenv("MAX_DATA_AGE", "14400"))
        min_stake_percentage = int(os.getenv("MIN_STAKE_PERCENTAGE", "33"))
        
        logger.info(f"Starting improved threshold relayer for query ID {query_id}")
        logger.info(f"Heartbeat interval: {sleep_time} seconds")
        logger.info(f"Price threshold: {price_threshold * 100}%")
        logger.info(f"Check interval: {check_interval} seconds")
        logger.info(f"Check time: {self.check_time} seconds")

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
        self.next_heartbeat_time = get_next_heartbeat_time(sleep_time, int(os.getenv("OFFSET", "5")))
        logger.info(f"Next heartbeat time: {self.next_heartbeat_time}")

        # main loop
        while True:
            try:
                # capture time + latest agg once per loop
                current_ts = int(time.time())
                latest_agg_report, e = self.get_latest_agg_report(query_id)
                if e:
                    logger.error(f"Error getting latest aggregate report: {e}")
                    sleep(check_interval)
                    continue

                # check layer chain status
                chain_status, error = get_layer_chain_status()
                if chain_status or error:
                    logger.warning(f"Layer chain status issue: {chain_status} or {error}")
                    sleep(check_interval)
                    continue

                # handle validator set updates
                e = handle_validator_set_update(evm)
                if e:
                    logger.error(f"Error handling validator set update: {e}")
                    sleep(check_interval)
                    continue

                # determine if we should tip
                should_tip, tip_reason = self.determine_should_tip(
                    current_ts, latest_agg_report, query_id, price_threshold, evm
                )
                if should_tip:
                    logger.info(f"Tipping: {tip_reason}")
                    self.tip_and_wait(query_data, current_ts)
                    if tip_reason.startswith("heartbeat"):
                        self.next_heartbeat_time = get_next_heartbeat_time(
                            sleep_time, int(os.getenv("OFFSET", "5"))
                        )
                        logger.info(f"Updated next heartbeat time: {self.next_heartbeat_time}")

                # determine if we should relay
                should_relay, relay_reason = self.determine_should_relay(
                    current_ts, latest_agg_report, query_id, price_threshold, evm, sleep_time
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
            sleep(check_interval)

    def get_latest_agg_report(self, query_id: str) -> tuple[dict, Exception]:
        """Get the latest aggregate report from Layer"""
        try:
            # try to get current aggregate report first
            report, e = get_current_aggregate_report(query_id)
            if e is None and report:
                return report, None
            
            # fallback to getting attestation data before current time
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
        
        # heartbeat tip (preferred)
        if current_ts > self.next_heartbeat_time:
            report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000  # convert ms to seconds
            if current_ts - report_ts > self.check_time:
                return True, f"heartbeat tip - current: {current_ts}, heartbeat: {self.next_heartbeat_time}, report age: {current_ts - report_ts}s"
        
        # threshold tip (only if no heartbeat tip)
        current_tip_amount = self.get_current_tip_amount(query_id)
        if current_tip_amount == 0:
            report_ts = int(latest_agg_report.get("timestamp", 0)) // 1000  # convert ms to seconds
            if current_ts - report_ts > 30:  # 30 seconds threshold
                try:
                    latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
                    if error or latest_relayed_data is None:
                        logger.debug("No previous relay data found for threshold comparison")
                        return False, "no previous relay data"
                    
                    real_price, error = get_current_price_from_api()
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
                             query_id: str, price_threshold: float, evm: EVMClient, 
                             sleep_time: int) -> tuple[bool, str]:
        """Determine if we should relay based on heartbeat or threshold logic"""
        
        try:
            latest_relayed_data, error = evm.get_last_relayed_data("TellorDataBank")
            if error:
                logger.error(f"Error getting last relayed data: {error}")
                return False, "error getting last relayed data"
            
            if latest_relayed_data is None:
                return True, "no previous relay data - initial relay"
            
            last_heartbeat_ts = self.get_heartbeat_ts_before(current_ts, sleep_time)
            relay_timestamp = latest_relayed_data.get("relay_timestamp", 0)
            
            # heartbeat relay
            if relay_timestamp < last_heartbeat_ts - self.check_time:
                return True, f"heartbeat relay - last relay: {relay_timestamp}, last heartbeat: {last_heartbeat_ts}"
            
            # threshold relay (consensus-gated / recent-consensus-gated)
            layer_val_checkpoint_params = self.get_layer_validator_checkpoint_params()
            if layer_val_checkpoint_params:
                aggregate_power = int(latest_agg_report.get("aggregate_power", 0))
                power_threshold = int(layer_val_checkpoint_params.get("power_threshold", 0))
                last_consensus_ts = int(latest_agg_report.get("last_consensus_timestamp", 0)) // 1000
                
                consensus_condition = (
                    aggregate_power > power_threshold or
                    current_ts - last_consensus_ts < sleep_time * 2
                )
                
                if consensus_condition:
                    real_price, error = get_current_price_from_api()
                    if error:
                        logger.error(f"Failed to get current price for threshold relay: {error}")
                        return False, "failed to get current price"
                    
                    price_change_pct = self.get_price_change_percentage(latest_relayed_data, real_price)
                    if price_change_pct >= price_threshold:
                        return True, f"threshold relay - price change: {price_change_pct*100:.2f}% >= {price_threshold*100:.2f}%"
        
        except Exception as e:
            logger.error(f"Error in relay determination logic: {e}")
        
        return False, "no relay needed"

    def get_current_tip_amount(self, query_id: str) -> int:
        """
        Get current tip amount for the query ID from Layer chain
        Returns 0 if no tip or error
        """
        try:
            query_data = os.getenv("QUERY_DATA")
            if not query_data:
                logger.error("QUERY_DATA not set in environment")
                return 0
            
            tip_data, error = get_current_tip(query_data)
            if error:
                logger.debug(f"No current tip found or error getting tip: {error}")
                return 0
            
            if tip_data and "amount" in tip_data:
                tip_amount = int(tip_data["amount"])
                logger.debug(f"Current tip amount for query: {tip_amount}")
                return tip_amount
            
            return 0
        except Exception as e:
            logger.error(f"Error getting current tip amount: {e}")
            return 0

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
                os.getenv("LAYER_RPC_ENDPOINT"), self.layer_chain_id, 10000)
            
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


def start_improved_threshold_relayer():
    """Entry point for the improved threshold relayer"""
    relayer = ImprovedThresholdRelayer()
    relayer.start_relayer()