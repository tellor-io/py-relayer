from src.layer_client import query_latest_oracle_data, strip_0x, get_current_aggregate_report
from src.evm_client import EVMClient
from src.transformer import transform_oracle_update_params
from src.relayer import handle_validator_set_update, get_oracle_data
from src.contract_adapters import get_contract_adapter
import time
import os
from dotenv import load_dotenv
import subprocess

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

    print(f"tipper: Starting tipper for contract type {CONTRACT_TYPE}...")
    
    # Initialize EVM client
    evm = EVMClient()
    evm.init_web3()
    evm.setup_blobstream_contract()
    
    # Setup the appropriate contract based on type
    if CONTRACT_TYPE == "SimpleLayerUser":
        evm.setup_layer_user_contract()
    elif CONTRACT_TYPE == "TestPriceFeedUser":
        evm.setup_layer_test_user_contract()
    else:
        print(f"tipper: Unsupported contract type: {CONTRACT_TYPE}")
        return
    
    print(f"tipper: Initialized EVM client with {CONTRACT_TYPE} contract")

    for i in range(N_ITERATIONS):
        e = handle_validator_set_update(evm)
        if e:
            print("tipper: Error handling validator set update: ", e)
            print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        
        start_time = time.time()
        previous_report, e = get_current_aggregate_report(QUERY_ID)
        if e:
            print("tipper: Error getting current aggregate report: ", e)
            print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        previous_report_timestamp = int(previous_report["timestamp"])
        print("tipper: start time: ", start_time)

        e = tip(QUERY_DATA, LAYER_ADDRESS, LAYER_RPC_ENDPOINT)
        if e:
            print("tipper: Error tipping: ", e)
            print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue

        # now query for the reported data and attestations
        report_timestamp = 0
        while report_timestamp <= previous_report_timestamp:
            time.sleep(250 / 1000)
            report, e = get_current_aggregate_report(QUERY_ID)
            if e:
                print("tipper: Error getting current aggregate report: ", e)
                print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
                time.sleep(ITERATION_SLEEP_TIME)
                continue
            report_timestamp = int(report["timestamp"])
            print("tipper: Report timestamp: ", report_timestamp)
        
        # Get oracle data
        oracle_data, e = get_oracle_data(QUERY_ID)
        if e:
            print("tipper: Error getting oracle data: ", e)
            print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        
        print("tipper: Oracle data retrieved")
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
                print("tipper: Error updating oracle data: ", e)
                print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
                time.sleep(ITERATION_SLEEP_TIME)
                continue
        else:
            print("tipper: Unexpected result from update_oracle_data: ", result)
            print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        
        print("tipper: Oracle data updated: ", tx_hash.hex())

        print("\ntipper: Time Report")
        print("start time: ", start_time)
        print("aggregate report time: ", report_timestamp)
        print("ready to relay time: ", ready_to_relay_time)
        print("diff ready-start: ", ready_to_relay_time - start_time)
        print("\n")
        print("tipper: Tipper finished")
        print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
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
        print("Tip result:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error executing tip command:")
        print(f"Exit code: {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise

if __name__ == "__main__":
    start_tipper()