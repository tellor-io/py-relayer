import time
import os
import requests
from eth_abi import decode
from src.layer_client import query_validator_set_update, query_latest_oracle_data, get_data_bridge_init_params, get_layer_latest_validator_timestamp, get_next_validator_set_timestamp, get_layer_chain_status, get_data_bridge_reset_params, query_latest_oracle_data, get_attestation_data_before, get_current_power_threshold, get_oracle_proof, get_layer_connection_status, get_layer_chain_id, get_data_before
from src.evm_client import EVMClient  # Only import the class
from src.transformer import transform_data_bridge_init_params, transform_valset_update_params, transform_oracle_update_params, transform_data_bridge_reset_params
from src.email_client import send_email_alert
from src.layer_tx_client import request_attestations
from src.logger_utils import get_logger

logger = get_logger(__name__)

VALSET_SLEEP_TIME = 1

# Global variables for threshold relayer
next_heartbeat_time = 0
pending_heartbeat_time = 0
last_tip_time = 0

def get_oracle_data(query_id):
    """
    Get oracle data for a specific query ID from tellor chain
    and transform it for the EVM contract
    
    Args:
        query_id: The query ID to get data for
    
    Returns:
        tuple: (oracle_data, error)
    """
    logger.info(f"Getting oracle data for query ID {query_id}")
    
    # Get oracle data from Layer chain
    oracle_data_response, error = query_latest_oracle_data(query_id)
    if error:
        return None, f"Failed to get oracle data: {error}"
    
    # Transform oracle data for EVM contract
    oracle_update_params = transform_oracle_update_params(oracle_data_response)
    
    return oracle_update_params, None

def get_oracle_data_optimized(query_id, optimistic_delay=900, max_attestation_age=600, max_data_age=14400, min_stake_percentage=33, last_relayed_timestamp=0) -> tuple[dict, Exception]:
    """
    Gets oracle data based on SamplePriceFeedUser preferences
    
    Args:
        query_id: The query ID to get data for
        optimistic_delay: The delay to use for optimistic data
        max_attestation_age: The maximum age of an attestation
        max_data_age: The maximum age of a report
        min_stake_percentage: The minimum stake percentage to use for optimistic data
        last_relayed_timestamp: The aggregate timestamp of the last relayed data (milliseconds) (optional)

    Returns:
        A tuple containing the oracle data and an exception if an error occurs

    Algorithm:
    - get latest report attestation data
    - if consensus, use this
        - check if report is older than last_relayed_timestamp. If so, return error (need a tip)
        - check data age. if greater than max_data_age, return error (need a tip)
        - check attestation age. if greater than max_attestation_age, request new attestations for this and relay
    - if not consensus, check if lastConsensusTimestamp is less than optimistic_delay age. If so, use this.
        - if attestation age is greater than max_attestation_age, request new attestations for this and relay
    - otherwise, getDataBefore(now - optimistic_delay)
        - if this report has more stake than min_stake_percentage, request new attestations for this and relay
    """
    logger.debug(f"Getting oracle data for query ID {query_id} with optimistic delay {optimistic_delay} max attestation age {max_attestation_age} max data age {max_data_age} min stake percentage {min_stake_percentage} last relayed timestamp {last_relayed_timestamp}")
    ADD_A_TIP = "Add a tip."
    # get latest attestation data
    attest_data, e = get_attestation_data_before(query_id, int(time.time()) * 1000)
    if e:
        return None, Exception(f"No data found. {ADD_A_TIP}")
    
    # make sure the aggregate data is going forward in time
    if last_relayed_timestamp > int(attest_data["timestamp"]):
        logger.debug(f"Latest report is >= last relayed timestamp. New data needed. Report timestamp: {attest_data['timestamp']} Last relayed timestamp: {last_relayed_timestamp}")
        return None, Exception(f"Latest report is >= last relayed timestamp. {ADD_A_TIP}")

    # determine which report to use
    opt_ts_ms = int(time.time() - optimistic_delay) * 1000 # optimistic timestamp
    if attest_data["last_consensus_timestamp"] == attest_data["timestamp"]:
        # is consensus
        logger.debug("Latest report is consensus")
    elif int(attest_data["last_consensus_timestamp"]) > opt_ts_ms:
        # last consensus timestamp is more recent than optimistic timestamp, use last consensus timestamp report
        # this report should never be too old, since MAX_DATA_AGE > OPTIMISTIC_DELAY
        # it should never be older than the last relayed timestamp. but it could be equal to it.
        logger.debug("Latest report is not consensus, but last consensus timestamp is less than optimistic delay")
        if int(attest_data["last_consensus_timestamp"]) <= last_relayed_timestamp:
            # if any optimistic data exists between last_relayed_timestamp and now, we should just exit and relay it once it's
            # older than the optimistic timestamp, since we don't want to keep tipping for optimistic data that we can't immediately relay
            # TODO: check all reports between last_relayed_timestamp and now
            current_power_threshold, e = get_current_power_threshold()
            if e:
                return None, e
            if int(attest_data["aggregate_power"]) > int(current_power_threshold) * 3/2 * min_stake_percentage / 100:
                # latest report has enough stake to be relayed after the optimistic timestamp
                return None, Exception("Relay after latest report passes optimistic timestamp")
            
        attest_data, e = get_attestation_data_before(query_id, int(attest_data["last_consensus_timestamp"]) + 1)
        if e:
            return None, e
    else:
        # no consensus, get data before now - optimistic_delay
        logger.debug("Latest report is not consensus, and last consensus timestamp is older than optimistic delay")
        attest_data, e = get_attestation_data_before(query_id, opt_ts_ms)
        if e:
            logger.error(f"Error getting attestation data before {opt_ts_ms}: {e}")
            return None, Exception(f"Error getting attestation data before {opt_ts_ms}: {e} {ADD_A_TIP}")
        current_power_threshold, e = get_current_power_threshold()
        if e:
            return None, e
        if int(attest_data["aggregate_power"]) < int(current_power_threshold) * 3/2 * int(min_stake_percentage) / 100:
            # report has too little stake
            logger.warning("Report has too little stake")
            # TODO: implement tip, request new report?

            return None, Exception("Report has too little stake. Add a tip.")
    
    # make sure the aggregate data is going forward in time
    if int(attest_data["timestamp"]) <= last_relayed_timestamp:
        logger.debug(f"Aggregate data is going backward in time. Report timestamp: {attest_data['timestamp']} Last relayed timestamp: {last_relayed_timestamp}")
        return None, Exception(f"Aggregate data is going backward in time. {ADD_A_TIP}")
    
    # check report age
    if int(time.time()) * 1000 - int(attest_data["timestamp"]) > max_data_age * 1000:
        # report is too old, no good data
        return None, Exception(f"Report is too old. Add a tip. Report timestamp: {attest_data['timestamp']} Current timestamp: {int(time.time()) * 1000}")
    
    # check attestation age
    if int(time.time()) * 1000 - int(attest_data["attestation_timestamp"]) > max_attestation_age * 1000:
        # attestation is too old, request new attestations
        logger.warning("Attestation is too old, requesting new attestations")
        layer_status, e = get_layer_connection_status()
        if e:
            return None, e
        chain_id = layer_status.get("result").get("node_info").get("network")
        e = request_attestations(query_id, attest_data["timestamp"], os.getenv("LAYER_ADDRESS"), os.getenv("LAYER_RPC_ENDPOINT"), chain_id)
        if e:
            return None, e
        sleep(3)

    # get the report and attestation data
    oracle_proof, e = get_oracle_proof_from_layer(query_id, attest_data["timestamp"])
    if e:
        return None, e
    
    # transform the oracle proof for the EVM contract
    oracle_update_params = transform_oracle_update_params(oracle_proof)

    return oracle_update_params, None

def update_user_oracle_data(query_id=None, contract_type="SimpleLayerUser", user_data=None):
    """
    Update oracle data for a specific query ID
    
    Args:
        query_id: The query ID to update
        contract_type: The type of contract to use (SimpleLayerUser, TestPriceFeedUser, etc.)
        user_data: Additional user-specific data needed by the adapter
    """
    if query_id is None:
        query_id = os.getenv("QUERY_ID")
    
    just_print = os.getenv("JUST_PRINT", "false").lower() == "true"
    logger.info(f"Updating oracle data for query ID {query_id} using {contract_type} contract...")
    
    # Initialize EVM client
    evm = EVMClient()
    evm.init_web3()
    
    # Get oracle data
    if contract_type == "TestPriceFeedUser":
        oracle_data, error = get_oracle_data_optimized(query_id)
    else:
        oracle_data, error = get_oracle_data(query_id)
    if error:
        logger.error(f"Error getting oracle data: {error}")
        return None, error
    
    if just_print:
        print_oracle_relay_for_etherscan(oracle_data["oracle_attestation_data"], oracle_data["current_validator_set"], oracle_data["sigs"])
        return None, None
    
    # Update oracle data using the appropriate contract
    tx_hash, e = evm.update_oracle_data(oracle_data, contract_type, user_data)
    if e:
        logger.error(f"Error updating oracle data: {e}")
        return None, e
    
    return tx_hash, None

def start_relayer():
    """Start the relayer process"""
    query_id = os.getenv("QUERY_ID")
    sleep_time = int(os.getenv("SLEEP_TIME", "600"))
    contract_type = os.getenv("CONTRACT_TYPE", "SimpleLayerUser")
    use_fixed_interval = os.getenv("FIXED_INTERVAL", "False").lower() == "true"
    
    logger.info(f"Starting relayer for query ID {query_id} using {contract_type} contract...")
    logger.info(f"Sleep time: {sleep_time} seconds")
    logger.info(f"Fixed interval mode: {use_fixed_interval}")

    evm = EVMClient()
    evm.init_web3()
    evm.setup_data_bridge_contract()
    
    while True:
        try:
            # Check layer chain status
            chain_status, error = get_layer_chain_status()
            if chain_status:
                logger.warning(f"Layer chain status: {chain_status}")
                if use_fixed_interval:
                    fixed_interval_sleep(sleep_time)
                else:
                    sleep(sleep_time)
                continue

            # Valset update
            e = handle_validator_set_update(evm)
            if e:
                logger.error(f"Error handling validator set update: {e}")
                if use_fixed_interval:
                    fixed_interval_sleep(sleep_time)
                else:
                    sleep(sleep_time)
                continue
            
            # Update oracle data
            user_trigger_timestamp = int(time.time())
            user_data = {"user_trigger_timestamp": user_trigger_timestamp}
            
            _, error = update_user_oracle_data(query_id, contract_type, user_data)
            if error:
                logger.error(f"Error updating oracle data: {error}")
                if use_fixed_interval:
                    fixed_interval_sleep(sleep_time)
                else:
                    sleep(sleep_time)
                continue
            
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
        # Sleep until next relay
        if use_fixed_interval:
            logger.debug(f"Using fixed interval sleep ({sleep_time}s)")
            fixed_interval_sleep(sleep_time)
        else:
            logger.debug(f"Using regular sleep ({sleep_time}s)")
            sleep(sleep_time)



def data_bridge_init(evm) -> Exception:
    logger.info("Initializing TellorDataBridge...")
    checkpoint_params, e = get_data_bridge_init_params()
    if e:
        return e
    logger.debug(f"Checkpoint params: {checkpoint_params}")
    init_tx_params = transform_data_bridge_init_params(checkpoint_params)
    logger.debug(f"Init tx params: {init_tx_params}")
    init_tx = evm.init_data_bridge(init_tx_params)  # Use evm instance method
    logger.info(f"Init tx: {init_tx}")
    return None

def data_bridge_reset(evm: EVMClient) -> Exception:
    logger.info("Resetting TellorDataBridge...")
    checkpoint_params, e = get_data_bridge_reset_params()
    if e:
        return e
    logger.debug(f"Checkpoint params: {checkpoint_params}")
    reset_tx_params = transform_data_bridge_reset_params(checkpoint_params)
    logger.debug(f"Reset tx params: {reset_tx_params}")
    
    just_print = os.getenv("JUST_PRINT", "false").lower() == "true"
    if just_print:
        print_reset_for_etherscan(reset_tx_params)
        return None
    
    evm.reset_data_bridge(reset_tx_params)  # Use evm instance method
    return None

def update_to_latest_layer_validator_set(evm: EVMClient, data_bridge_validator_timestamp: str, layer_validator_timestamp: str) -> Exception:
    while int(data_bridge_validator_timestamp) < int(layer_validator_timestamp):
        next_validator_timestamp, e = get_next_validator_set_timestamp(data_bridge_validator_timestamp)
        if e:
            return e
        valset_update_params, e = query_validator_set_update(next_validator_timestamp)
        if e:
            return e
        logger.debug(f"Valset update params: {valset_update_params}")
        valset_update_tx_params = transform_valset_update_params(valset_update_params)
        logger.debug(f"Valset update tx params: {valset_update_tx_params}")
        _, e = evm.update_validator_set(valset_update_tx_params)  # Use evm instance method
        if e:
            return e
        logger.info("Submitted valset update tx")
        sleep(VALSET_SLEEP_TIME)
        layer_validator_timestamp, e = get_layer_latest_validator_timestamp()
        if e:
            return e
        data_bridge_validator_timestamp = evm.get_data_bridge_validator_timestamp()
        logger.debug(f"TellorDataBridge validator timestamp: {data_bridge_validator_timestamp}")

    logger.info("TellorDataBridge valset up to date with Layer valset")
    return None

def update_user_oracle_data_2(evm, query_id) -> Exception:
    logger.info("Updating oracle data...")
    oracle_proof, e = query_latest_oracle_data(query_id)
    if e:
        return e
    current_price_data_timestamp = evm.get_current_price_data_timestamp()  # Use evm instance method
    logger.debug(f"Current price data timestamp: {current_price_data_timestamp}")
    logger.debug(f"Oracle proof: {oracle_proof}")
    if int(oracle_proof["attestation_data"]["timestamp"]) > int(current_price_data_timestamp):
        logger.info("New oracle data available, updating...")
        
    return None

def check_layer_chain_status() -> Exception:
    if os.getenv("EMAIL_PASSWORD") is None:
        return None
    message, e = get_layer_chain_status()
    if message is not None:
        logger.warning(f"Layer chain status message: {message}")
        e = send_email_alert("Layer chain status alert", message)
        if e:
            return e
    return None

def handle_validator_set_update(evm) -> Exception:
    layer_validator_timestamp, e = get_layer_latest_validator_timestamp()
    if e:
        logger.error(f"Error getting latest Layer validator timestamp: {e}")
        return e
    logger.debug(f"Layer validator timestamp: {layer_validator_timestamp}")
    data_bridge_validator_timestamp = evm.get_data_bridge_validator_timestamp()
    logger.debug(f"TellorDataBridge validator timestamp: {data_bridge_validator_timestamp}")
    if int(data_bridge_validator_timestamp) < int(layer_validator_timestamp):
        logger.info("Updating to latest Layer validator set...")
        e = update_to_latest_layer_validator_set(evm, data_bridge_validator_timestamp, layer_validator_timestamp)
        if e:
            logger.error(f"Error updating to latest Layer validator set: {e}")
            return e
        
def sleep(seconds: int) -> None:
    logger.debug(f"Sleeping for {seconds} seconds")
    time.sleep(seconds)
    return None

def fixed_interval_sleep(interval_seconds: int, offset: int = 5) -> None:
    """
    Sleep for a fixed interval, starting from 1/1/2025 00:00:00 GMT
    """
    current_time = time.time()
    next_heartbeat_time = get_next_heartbeat_time(interval_seconds, offset)
    sleep_duration = next_heartbeat_time - current_time
    
    # Safety check to prevent negative sleep times
    if sleep_duration < 0:
        logger.warning(f"Calculated negative sleep duration: {sleep_duration:.2f}s, sleeping for 0")
        sleep_duration = 0
    
    logger.debug(f"Fixed interval sleep: {sleep_duration:.2f}s until next {interval_seconds}s boundary")
    time.sleep(sleep_duration)
    return None

def get_next_heartbeat_time(interval_seconds: int, offset: int = 5) -> int:
    """
    Get the next heartbeat time for a fixed interval
    The basis time is 1/1/2025 00:00:00 GMT, or 1735689600

    Args:
        interval_seconds: The interval in seconds
        offset: The offset in seconds

    Returns:
        The next heartbeat time
    """
    current_time = time.time()
    # Basis time is 1/1/2025 00:00:00 GMT, or 1735689600
    # Plus 5 seconds since sepolia's next block after 00:00:00 is consistently at 00:00:12
    # This gives time to be try to be included in the next eth block
    # TODO: make this offset configurable
    basis_time = 1735689600 + offset
    diff = current_time - basis_time
    next_heartbeat_time = int(diff / interval_seconds) * interval_seconds + interval_seconds + basis_time
    return next_heartbeat_time

def print_oracle_relay_for_etherscan(attest_data, validator_set, sigs):
    # Format _attestData
    query_id = "0x" + attest_data['queryId'].hex()
    report = attest_data['report']
    value = "0x" + report['value'].hex()
    
    report_formatted = f'["{value}","{report["timestamp"]}","{report["aggregatePower"]}","{report["previousTimestamp"]}","{report["nextTimestamp"]}","{report["lastConsensusTimestamp"]}"]'
    
    # Format _currentValidatorSet
    validators_formatted = "[" + ",".join(f'["{v["addr"]}","{v["power"]}"]' for v in validator_set) + "]"
    
    # Format _sigs
    sigs_formatted = "[" + ",".join(
        f'["{sig["v"]}","0x{sig["r"].hex()}","0x{sig["s"].hex()}"]' 
        for sig in sigs
    ) + "]"
    
    print("\n\n\n\n")
    print("===== START OF FORMATTED PARAMETERS FOR ETHERSCAN =====")
    print("\n1. _attestData (tuple):")
    print(f"1a. queryId:")
    print(query_id)
    print(f"1b. report (tuple):")
    print(report_formatted)
    print(f"1c. attestationTimestamp:")
    print(attest_data['attestationTimestamp'])
    print("\n2. _currentValidatorSet (tuple[]):")
    print(validators_formatted)
    print("\n3. _sigs (tuple[]):")
    print(sigs_formatted)
    print("\n===== END OF FORMATTED PARAMETERS FOR ETHERSCAN =====\n\n\n\n")

def print_reset_for_etherscan(reset_tx_params):
    from web3 import Web3
    
    power_threshold = reset_tx_params["power_threshold"]
    validator_timestamp = reset_tx_params["validator_timestamp"]
    validator_set_checkpoint = reset_tx_params["validator_set_checkpoint"]
    
    # Format individual parameters for etherscan
    print("\n\n\n\n")
    print("===== START OF FORMATTED PARAMETERS FOR ETHERSCAN =====")
    print("\n1. _powerThreshold (uint256):")
    print(power_threshold)
    print("\n2. _validatorTimestamp (uint256):")
    print(validator_timestamp)
    print("\n3. _validatorSetCheckpoint (bytes32):")
    print("0x" + validator_set_checkpoint.hex())
    print("\n====== END OF FORMATTED PARAMETERS FOR ETHERSCAN ======")
    
    # Generate function selector for guardianResetValidatorSet(uint256,uint256,bytes32)
    function_signature = "guardianResetValidatorSet(uint256,uint256,bytes32)"
    function_selector = Web3.keccak(text=function_signature)[:4]
    
    # Encode the parameters using eth_abi directly
    from eth_abi import encode
    encoded_params = encode(
        ["uint256", "uint256", "bytes32"],
        [power_threshold, validator_timestamp, validator_set_checkpoint]
    )
    
    # Combine function selector and encoded parameters
    full_calldata = function_selector.hex() + encoded_params.hex()
    
    print("\n\n\n\n============ COMPLETE TRANSACTION CALLDATA ============")
    print("\nFunction: \nguardianResetValidatorSet(uint256,uint256,bytes32)")
    print("\nComplete calldata (hex):")
    print(full_calldata)
    print("\n============= END OF TRANSACTION CALLDATA =============\n\n\n\n")

def get_current_price_from_api() -> tuple[float, Exception]:
    """
    Get the current price from the API or Layer chain
    """
    api_url = os.getenv("PRICE_API_URL")
    
    if api_url:
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"API response: {data}")
                # Handle different API response formats
                if "usd" in data:
                    logger.debug(f"Price from API: {data['usd']}")
                    return float(data["usd"]), None
                elif isinstance(data, list) and len(data) > 0 and "usd" in data[0]:
                    logger.debug(f"Price from API: {data[0]['usd']}")
                    return float(data[0]["usd"]), None
                # Handle CoinGecko format: {'bitcoin': {'usd': 116918}}
                elif isinstance(data, dict):
                    for coin_name, coin_data in data.items():
                        if isinstance(coin_data, dict) and "usd" in coin_data:
                            logger.debug(f"Price from API ({coin_name}): {coin_data['usd']}")
                            return float(coin_data["usd"]), None
                
                logger.warning(f"Unexpected API response format: {data}")
                return None, Exception(f"Unexpected API response format: {data}")
        except Exception as e:
            logger.warning(f"Failed to get price from API: {e}")
            return None, Exception(f"Failed to get price from API: {e}")
    
    # Fallback to Layer chain data
    logger.info("Falling back to Layer chain for current price")
    try:
        query_id = os.getenv("QUERY_ID")
        oracle_data, error = query_latest_oracle_data(query_id)
        if error:
            logger.error(f"Failed to get price from Layer: {error}")
            return None, error
        
        # Decode price from oracle data
        value_hex = oracle_data["attestation_data"]["aggregate_value"]
        value_bytes = bytes.fromhex(value_hex)
        value_decoded = decode(["uint256"], value_bytes)
        return float(value_decoded[0])/10**18, None
    except Exception as e:
        logger.error(f"Failed to get price from Layer: {e}")
        return None, Exception(f"Failed to get price from Layer: {e}")

def get_oracle_proof_from_layer(query_id: str, timestamp: int) -> tuple[dict, Exception]:
    """
    Get oracle proof from layer by queryId and timestamp
    If checkpoint mismatch, request new attestations and retry
    """
    oracle_data, error = get_oracle_proof(query_id, timestamp)
    if error is None:
        return oracle_data, None
    if str(error) != "layer_client: Checkpoint mismatch":
        return None, error
    
    # request new attestations
    chain_id, e = get_layer_chain_id()
    if e:
        return None, e
    
    e = request_attestations(query_id, timestamp, os.getenv("LAYER_ADDRESS"), os.getenv("LAYER_RPC_ENDPOINT"), chain_id)
    if e:
        return None, e
    sleep(5)

    return get_oracle_proof(query_id, timestamp)

def get_latest_oracle_proof_from_layer(query_id: str) -> tuple[dict, Exception]:
    """
    Get latest oracle proof from layer by queryId
    If checkpoint mismatch, request new attestations and retry
    """
    current_time = int(time.time()) * 1000
    report, e = get_data_before(query_id, current_time)
    if e:
        return None, e
    if report is None or "timestamp" not in report:
        return None, Exception("layer_client: No data found")
    return get_oracle_proof_from_layer(query_id, report["timestamp"])