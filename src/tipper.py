from src.layer_client import query_latest_oracle_data, strip_0x, get_current_aggregate_report
from src.evm_client import EVMClient
from src.transformer import transform_oracle_update_params
from src.relayer import handle_validator_set_update, get_oracle_data
from src.contract_adapters import get_contract_adapter
import time
import os
from dotenv import load_dotenv
import subprocess
from src.logger_utils import get_logger

logger = get_logger(__name__)

# load_dotenv()

# QUERY_ID = os.getenv("QUERY_ID")
# QUERY_DATA = os.getenv("QUERY_DATA")
# SLEEP_TIME = int(os.getenv("SLEEP_TIME"))
# LAYER_ADDRESS = os.getenv("LAYER_ADDRESS")
# LAYER_RPC_ENDPOINT = os.getenv("LAYER_RPC_ENDPOINT")
# CONTRACT_TYPE = os.getenv("CONTRACT_TYPE", "SimpleLayerUser")
# N_ITERATIONS = 50
# ITERATION_SLEEP_TIME = 120 # seconds between iterations

def start_tipper():
    QUERY_ID = os.getenv("QUERY_ID")
    QUERY_DATA = os.getenv("QUERY_DATA")
    LAYER_ADDRESS = os.getenv("LAYER_ADDRESS")
    LAYER_RPC_ENDPOINT = os.getenv("LAYER_RPC_ENDPOINT")
    CONTRACT_TYPE = os.getenv("CONTRACT_TYPE", "SimpleLayerUser")
    N_ITERATIONS = 50
    ITERATION_SLEEP_TIME = int(os.getenv("SLEEP_TIME", 3600)) # seconds between iterations

    logger.info(f"Starting tipper for contract type {CONTRACT_TYPE}...")
    
    # Initialize EVM client
    evm = EVMClient()
    evm.init_web3()
    evm.setup_data_bridge_contract()
    
    # Setup the appropriate contract based on type
    if CONTRACT_TYPE == "SimpleLayerUser":
        evm.setup_layer_user_contract()
    elif CONTRACT_TYPE == "TestPriceFeedUser":
        evm.setup_layer_test_user_contract()
    else:
        logger.error(f"Unsupported contract type: {CONTRACT_TYPE}")
        return
    
    logger.info(f"Initialized EVM client with {CONTRACT_TYPE} contract")

    for i in range(N_ITERATIONS):
        e = handle_validator_set_update(evm)
        if e:
            logger.error(f"Error handling validator set update: {e}")
            logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        
        start_time = time.time()
        previous_report, e = get_current_aggregate_report(QUERY_ID)
        if e:
            logger.error(f"Error getting current aggregate report: {e}")
            logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        previous_report_timestamp = int(previous_report["timestamp"])
        logger.info(f"Start time: {start_time}")

        e = tip(QUERY_DATA, LAYER_ADDRESS, LAYER_RPC_ENDPOINT)
        if e:
            logger.error(f"Error tipping: {e}")
            logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue

        # now query for the reported data and attestations
        report_timestamp = 0
        while report_timestamp <= previous_report_timestamp:
            time.sleep(250 / 1000)
            report, e = get_current_aggregate_report(QUERY_ID)
            if e:
                logger.error(f"Error getting current aggregate report: {e}")
                logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
                time.sleep(ITERATION_SLEEP_TIME)
                continue
            report_timestamp = int(report["timestamp"])
            logger.info(f"Report timestamp: {report_timestamp}")
        
        # Get oracle data
        oracle_data, e = get_oracle_data(QUERY_ID)
        if e:
            logger.error(f"Error getting oracle data: {e}")
            logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        
        logger.info("Oracle data retrieved")
        ready_to_relay_time = time.time()
        
        # Get the appropriate adapter and prepare user data
        user_data = {
            "begin_relay_timestamp": int(start_time),
            "init_timestamp": int(start_time)
        }
        
        # Update oracle data using the appropriate contract
        result = evm.update_oracle_data(oracle_data, CONTRACT_TYPE, user_data)
        if isinstance(result, tuple) and len(result) == 2:
            tx_hash, e = result
            if e:
                logger.error(f"Error updating oracle data: {e}")
                logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
                time.sleep(ITERATION_SLEEP_TIME)
                continue
        else:
            logger.error(f"Unexpected result from update_oracle_data: {result}")
            logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        
        logger.info(f"Oracle data updated: {tx_hash.hex()}")

        logger.info("Time Report")
        logger.info(f"start time: {start_time}")
        logger.info(f"aggregate report time: {report_timestamp}")
        logger.info(f"ready to relay time: {ready_to_relay_time}")
        logger.info(f"diff ready-start: {ready_to_relay_time - start_time}")
        logger.info("\n")
        logger.info("Tipper finished")
        logger.info(f"Sleeping for {ITERATION_SLEEP_TIME} seconds")
        time.sleep(ITERATION_SLEEP_TIME)

def tip(query_data, layer_address, layer_rpc_endpoint) -> Exception:
    # Remove '0x' prefix if it exists
    query_data_stripped = strip_0x(query_data)
    
    try:
        result = subprocess.run(
            ["layerd", "tx", "oracle", "tip",
             layer_address,  
             query_data_stripped,
             "100000loya", 
             "--from", layer_address, 
             "--chain-id", "layertest-3", 
             "--fees", "5loya", 
             "--keyring-backend", "test", 
             "--yes", 
             "--node=" + layer_rpc_endpoint],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Tip result:")
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("Error executing tip command:")
        logger.error(f"Exit code: {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise

if __name__ == "__main__":
    start_tipper()