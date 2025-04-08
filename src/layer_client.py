# layer_client.py
import requests
import time
import os
from dateutil import parser

def strip_0x(value):
    if value.startswith("0x"):
        return value[2:]
    return value

def get_layer_connection_status() -> tuple[str, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    rpc_endpoint = os.getenv("LAYER_RPC_ENDPOINT")
    print("layer_client: Getting layer connection status")
    print("layer_client: swagger endpoint: ", swagger_endpoint)
    print("layer_client: rpc endpoint: ", rpc_endpoint)
    request = f"{rpc_endpoint}/status"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting layer connection status: {e}")
        return None, e

def get_layer_chain_status() -> tuple[str, Exception]:
    rpc_endpoint = os.getenv("LAYER_RPC_ENDPOINT")
    request = f"{rpc_endpoint}/status"
    try:
        response = requests.get(request)
        if response.status_code != 200:
            message = f"layer_client: Error getting layer chain status: {response.status_code}"
            return message, None
        catching_up_status = response.json().get("result").get("sync_info").get("catching_up")
        if catching_up_status == "true":
            message = "layer_client: Layer chain is catching up"
            return message, None
        latest_block_time_str = response.json().get("result").get("sync_info").get("latest_block_time") 
        latest_block_time = parser.parse(latest_block_time_str)
        latest_block_time = latest_block_time.timestamp()
        current_time = int(time.time())
        time_diff = current_time - latest_block_time
        if time_diff > 60:
            message = "layer_client: Latest block more than 1 minute old"
            return message, None
        return None, None
    except Exception as e:
        message = f"layer_client: Error getting layer chain status: {e}"
        return message, e
    
def get_layer_chain_id() -> tuple[str, Exception]:
    layer_status, e = get_layer_connection_status()
    if e:
        return None, e
    return layer_status.get("result").get("node_info").get("network"), None

# validator set functions
def get_validator_timestamp_by_index(index: int) -> tuple[dict, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_validator_timestamp_by_index/{index}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator timestamp by index: {e}")
        return None, e

def get_validator_checkpoint_params(timestamp: int) -> tuple[dict, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_validator_checkpoint_params/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator checkpoint params: {e}")
        return None, e

def get_valset_by_timestamp(timestamp: int) -> tuple[dict, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_valset_by_timestamp/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator set by timestamp: {e}")
        return None, e

def get_valset_sigs(timestamp: int) -> tuple[dict, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_valset_sigs/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator set sigs: {e}")
        return None, e

def get_current_validator_set_timestamp() -> tuple[str, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_current_validator_set_timestamp"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting current validator set timestamp: {e}")
        return None, e

def get_validator_set_index_by_timestamp(timestamp: int) -> tuple[dict, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_validator_set_index_by_timestamp/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator set index by timestamp: {e}")
        return None, e

# oracle data functions 
def get_data_before(query_id: str, timestamp_before: int) -> tuple[dict, Exception]:
    query_id = strip_0x(query_id)
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/tellor-io/layer/oracle/get_data_before/{query_id}/{timestamp_before}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting data before: {e}")
        return None, e
    
def get_reports_by_aggregate(query_id: str, timestamp: int) -> tuple[dict, Exception]:
    query_id = strip_0x(query_id)
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/tellor-io/layer/oracle/get_reports_by_aggregate/{query_id}/{timestamp}?pagination.limit=10000"
    print(f"layer_client: Request: {request}")
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting reports by aggregate: {e}")
        return None, e
    
def get_current_aggregate_report(query_id: str) -> tuple[dict, Exception]:
    query_id = strip_0x(query_id)
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/tellor-io/layer/oracle/get_current_aggregate_report/{query_id}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting current aggregate report: {e}")
        return None, e

def get_snapshots_by_report(query_id: str, timestamp: int) -> tuple[dict, Exception]:
    query_id = strip_0x(query_id)
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_snapshots_by_report/{query_id}/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting snapshots by report: {e}")
        return None, e

def get_attestations_by_snapshot(snapshot: str) -> tuple[dict, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_attestations_by_snapshot/{snapshot}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting attestations by snapshot: {e}")
        return None, e

def get_attestation_data_by_snapshot(snapshot: str) -> tuple[dict, Exception]:
    swagger_endpoint = os.getenv("LAYER_SWAGGER_ENDPOINT")
    request = f"{swagger_endpoint}/layer/bridge/get_attestation_data_by_snapshot/{snapshot}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting attestation data by snapshot: {e}")
        return None, e

## queries

def query_latest_oracle_data(query_id: str) -> tuple[dict, Exception]:
    print("layer_client: Querying latest oracle data")
    # subtract 1 second to account for attestation time,
    # TODO: optimize
    current_time = int(time.time()) * 1000 - 1000 
    report, e = get_data_before(query_id, current_time)
    if e:
        return None, e
    return get_oracle_proof(query_id, report["timestamp"])

def get_attestation_data_before(query_id: str, timestamp: int) -> tuple[dict, Exception]:
    print(f"layer_client: Querying attestation data before {timestamp}")
    report, e = get_data_before(query_id, timestamp)
    if e:
        return None, e
    snapshots, e = get_snapshots_by_report(query_id, report["timestamp"])
    if e:
        return None, e
    last_snapshot = snapshots["snapshots"][-1]
    attestation_data, e = get_attestation_data_by_snapshot(last_snapshot)
    if e:
        return None, e
    print(f"layer_client: Attestation data: {attestation_data}")
    return attestation_data, None

def get_oracle_proof(query_id: str, timestamp: int) -> tuple[dict, Exception]:
    print(f"layer_client: Querying oracle proof for {timestamp}")
    snapshots, e = get_snapshots_by_report(query_id, timestamp)
    if e:
        return None, e
    last_snapshot = snapshots["snapshots"][-1]
    attestations, e = get_attestations_by_snapshot(last_snapshot)
    if e:
        return None, e
    attestation_data, e = get_attestation_data_by_snapshot(last_snapshot)
    if e:
        return None, e
    current_validator_set, e = get_current_validator_set()
    if e:
        return None, e
    threshold, e = get_current_power_threshold()
    if e:
        return None, e
    sufficient_power = get_sufficient_attestation_power(
        attestations.get("attestations"), 
        current_validator_set.get("bridge_validator_set"), 
        threshold
    )
    if not sufficient_power:
        retry_sleep_time = 3
        retry_count = 0
        while retry_count < 3:
            print(f"layer_client: Insufficient attestation power, sleeping for {retry_sleep_time} seconds")
            time.sleep(retry_sleep_time)
            attestations, e = get_attestations_by_snapshot(last_snapshot)
            if e:
                return None, e
            retry_count += 1
            sufficient_power = get_sufficient_attestation_power(
                attestations.get("attestations"), 
                current_validator_set.get("bridge_validator_set"), 
                threshold
            )
            if sufficient_power:
                break
            retry_sleep_time = int(retry_sleep_time * 1.5)
        if not sufficient_power:
            return None, Exception("layer_client: Insufficient attestation power")
    oracle_proof = {
        "attestations": attestations,
        "attestation_data": attestation_data,
        "validator_set": current_validator_set,
        "snapshot": last_snapshot
    }
    return oracle_proof, None

def get_sufficient_attestation_power(attestations: list[dict], current_validator_set: dict, threshold: int) -> bool:
    power_sum = 0
    for i in range(len(attestations)):
        if len(attestations[i]) > 0:
            power_sum += int(current_validator_set[i]["power"])
    return power_sum >= int(threshold)

def get_next_validator_set_timestamp(given_timestamp: int) -> tuple[str, Exception]:
    given_ts_index, e = get_validator_set_index_by_timestamp(given_timestamp)
    if e:
        return None, e
    if given_ts_index is None or "index" not in given_ts_index:
        return None, Exception("layer_client: Invalid timestamp")
    next_ts_index = str(int(given_ts_index.get("index")) + 1)
    next_ts, e = get_validator_timestamp_by_index(next_ts_index)
    if e:
        return None, e
    return next_ts.get("timestamp"), None

def get_previous_validator_set_timestamp(given_timestamp: int) -> tuple[str, Exception]:
    given_ts_index, e = get_validator_set_index_by_timestamp(given_timestamp)
    if e:
        return None, e
    if given_ts_index is None or "index" not in given_ts_index:
        return None, Exception("layer_client: Invalid timestamp")
    previous_ts_index = str(int(given_ts_index.get("index")) - 1)
    previous_ts, e = get_validator_timestamp_by_index(previous_ts_index)
    if e:
        return None, e
    if previous_ts is None or "timestamp" not in previous_ts:
        return None, Exception("layer_client: Invalid timestamp")
    return previous_ts.get("timestamp"), None

def query_validator_set_update(given_timestamp: int) -> tuple[dict, Exception]:
    valset_sigs, e = get_valset_sigs(given_timestamp)
    if e:
        return None, e
    valset_checkpoint, e = get_validator_checkpoint_params(given_timestamp)
    if e:
        return None, e
    previous_timestamp, e = get_previous_validator_set_timestamp(given_timestamp)
    if e:
        return None, e
    previous_valset, e = get_valset_by_timestamp(previous_timestamp)
    if e:
        return None, e
    valset_update_params = {
        "valset_sigs": valset_sigs,
        "valset_checkpoint": valset_checkpoint,
        "previous_valset": previous_valset
    }
    return valset_update_params, None

def get_blobstream_init_params() -> tuple[dict, Exception]:
    first_timestamp, e = get_validator_timestamp_by_index(0)
    if e:
        return None, e
    checkpoint_params, e = get_validator_checkpoint_params(first_timestamp.get("timestamp"))
    if e:
        return None, e
    return checkpoint_params, None

def get_blobstream_reset_params() -> tuple[dict, Exception]:
    latest_timestamp, e = get_layer_latest_validator_timestamp()
    checkpoint_params, e = get_validator_checkpoint_params(latest_timestamp)
    if e:
        return None, e
    return checkpoint_params, None

def get_layer_latest_validator_timestamp() -> tuple[str, Exception]:
    latest_timestamp, e = get_current_validator_set_timestamp()
    if e:
        return None, e
    return latest_timestamp.get("timestamp"), None

def get_current_validator_set() -> tuple[dict, Exception]:
    latest_timestamp, e = get_layer_latest_validator_timestamp()
    if e:
        return None, e
    valset, e = get_valset_by_timestamp(latest_timestamp)
    if e:
        return None, e
    return valset, None

def get_current_power_threshold() -> tuple[int, Exception]:
    latest_timestamp, e = get_layer_latest_validator_timestamp()
    if e:
        return None, e
    checkpoint_params, e = get_validator_checkpoint_params(latest_timestamp)
    print("checkpoint_params: ", checkpoint_params)
    if e:
        return None, e
    return checkpoint_params.get("power_threshold"), None

