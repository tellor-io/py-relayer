# layer_client.py
import requests
import time

rpc_endpoint = "http://localhost:1317"

def strip_0x(value):
    if value.startswith("0x"):
        return value[2:]
    return value

# validator set functions
def get_validator_timestamp_by_index(index) -> (dict, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_validator_timestamp_by_index/{index}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator timestamp by index: {e}")
        return None, e

def get_validator_checkpoint_params(timestamp) -> (dict, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_validator_checkpoint_params/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator checkpoint params: {e}")
        return None, e

def get_valset_by_timestamp(timestamp) -> (dict, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_valset_by_timestamp/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator set by timestamp: {e}")
        return None, e

def get_valset_sigs(timestamp) -> (dict, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_valset_sigs/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator set sigs: {e}")
        return None, e

def get_current_validator_set_timestamp() -> (str, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_current_validator_set_timestamp"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting current validator set timestamp: {e}")
        return None, e

def get_validator_set_index_by_timestamp(timestamp) -> (dict, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_validator_set_index_by_timestamp/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting validator set index by timestamp: {e}")
        return None, e

# oracle data functions 
def get_data_before(query_id, timestamp_before) -> (dict, Exception):
    query_id = strip_0x(query_id)
    request = f"{rpc_endpoint}/tellor-io/layer/oracle/get_data_before/{query_id}/{timestamp_before}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting data before: {e}")
        return None, e

def get_snapshots_by_report(query_id, timestamp) -> (dict, Exception):
    query_id = strip_0x(query_id)
    request = f"{rpc_endpoint}/layer/bridge/get_snapshots_by_report/{query_id}/{timestamp}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting snapshots by report: {e}")
        return None, e

def get_attestations_by_snapshot(snapshot) -> (dict, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_attestations_by_snapshot/{snapshot}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting attestations by snapshot: {e}")
        return None, e

def get_attestation_data_by_snapshot(snapshot) -> (dict, Exception):
    request = f"{rpc_endpoint}/layer/bridge/get_attestation_data_by_snapshot/{snapshot}"
    try:
        response = requests.get(request)
        return response.json(), None
    except Exception as e:
        print(f"layer_client: Error getting attestation data by snapshot: {e}")
        return None, e

## queries

def query_latest_oracle_data(query_id) -> (dict, Exception):
    # subtract 1 second to account for attestation time,
    # TODO: optimize
    current_time = int(time.time()) * 1000 - 1000 
    report, e = get_data_before(query_id, current_time)
    if e:
        return None, e
    snapshots, e = get_snapshots_by_report(query_id, report["timestamp"])
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
    oracle_proof = {
        "attestations": attestations,
        "attestation_data": attestation_data,
        "validator_set": current_validator_set,
        "snapshot": last_snapshot
    }
    return oracle_proof, None

def get_next_validator_set_timestamp(given_timestamp) -> (str, Exception):
    given_ts_index, e = get_validator_set_index_by_timestamp(given_timestamp)
    if e:
        return None, e
    next_ts_index = str(int(given_ts_index.get("index")) + 1)
    next_ts, e = get_validator_timestamp_by_index(next_ts_index)
    if e:
        return None, e
    return next_ts.get("timestamp"), None

def get_previous_validator_set_timestamp(given_timestamp) -> (str, Exception):
    given_ts_index, e = get_validator_set_index_by_timestamp(given_timestamp)
    if e:
        return None, e
    previous_ts_index = str(int(given_ts_index.get("index")) - 1)
    previous_ts, e = get_validator_timestamp_by_index(previous_ts_index)
    if e:
        return None, e
    return previous_ts.get("timestamp"), None

def query_validator_set_update(given_timestamp) -> (dict, Exception):
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

def get_blobstream_init_params() -> (dict, Exception):
    first_timestamp, e = get_validator_timestamp_by_index(0)
    if e:
        return None, e
    checkpoint_params, e = get_validator_checkpoint_params(first_timestamp.get("timestamp"))
    if e:
        return None, e
    return checkpoint_params, None

def get_layer_latest_validator_timestamp() -> (str, Exception):
    latest_timestamp, e = get_current_validator_set_timestamp()
    if e:
        return None, e
    return latest_timestamp.get("timestamp"), None

def get_current_validator_set() -> (dict, Exception):
    latest_timestamp, e = get_layer_latest_validator_timestamp()
    if e:
        return None, e
    valset, e = get_valset_by_timestamp(latest_timestamp)
    if e:
        return None, e
    return valset, None

