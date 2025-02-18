from src.layer_client import query_latest_oracle_data, strip_0x, get_current_aggregate_report
from src.evm_client import EVMClient
from src.transformer import transform_oracle_update_params
from src.relayer import handle_validator_set_update
import time
import os
from dotenv import load_dotenv
import subprocess

load_dotenv()

QUERY_ID = os.getenv("QUERY_ID")
QUERY_DATA = os.getenv("QUERY_DATA")
SLEEP_TIME = int(os.getenv("SLEEP_TIME"))
LAYER_ADDRESS = os.getenv("LAYER_ADDRESS")
LAYER_RPC_ENDPOINT = os.getenv("LAYER_RPC_ENDPOINT")
N_ITERATIONS = 50
ITERATION_SLEEP_TIME = 120 # seconds between iterations

def start_tipper():
    print("tipper: Starting tipper...")
    
    # Initialize EVM client
    evm = EVMClient()
    evm.init_web3()
    evm.setup_blobstream_contract()
    evm.setup_layer_user_contract()
    print("tipper: Initialized EVM client")

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

        e = tip(QUERY_DATA)
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
        
        oracle_proof, e = query_latest_oracle_data(QUERY_ID)
        if e:
            print("tipper: Error getting oracle data: ", e)
            print("tipper: Sleeping for ", ITERATION_SLEEP_TIME, " seconds")
            time.sleep(ITERATION_SLEEP_TIME)
            continue
        print("tipper: Report proof: ", oracle_proof)
        oracle_update_tx_params = transform_oracle_update_params(oracle_proof)
        print("tipper: Oracle update tx params: ", oracle_update_tx_params)
        ready_to_relay_time = time.time()
        tx_hash, e = evm.update_oracle_data(oracle_update_tx_params)
        if e:
            print("tipper: Error updating oracle data: ", e)
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

def tip(query_data) -> Exception:
    # Remove '0x' prefix if it exists
    query_data_stripped = strip_0x(query_data)
    
    try:
        result = subprocess.run(
            ["layerd", "tx", "oracle", "tip",
             LAYER_ADDRESS,  
             query_data_stripped,
             "100000loya", 
             "--from", LAYER_ADDRESS, 
             "--chain-id", "layertest-3", 
             "--fees", "5loya", 
             "--keyring-backend", "test", 
             "--yes", 
             "--node=" + LAYER_RPC_ENDPOINT],
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