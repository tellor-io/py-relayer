# layer_client.py
import requests
import time

rpc_endpoint = "http://localhost:1317"

def strip_0x(value):
    if value.startswith("0x"):
        return value[2:]
    return value

# validator set functions
def get_validator_timestamp_by_index(index):
    request = f"{rpc_endpoint}/layer/bridge/get_validator_timestamp_by_index/{index}"
    response = requests.get(request)
    return response.json()

def get_validator_checkpoint_params(timestamp):
    request = f"{rpc_endpoint}/layer/bridge/get_validator_checkpoint_params/{timestamp}"
    response = requests.get(request)
    return response.json()

def get_valset_by_timestamp(timestamp):
    request = f"{rpc_endpoint}/layer/bridge/get_valset_by_timestamp/{timestamp}"
    response = requests.get(request)
    return response.json()

def get_valset_sigs(timestamp):
    request = f"{rpc_endpoint}/layer/bridge/get_valset_sigs/{timestamp}"
    response = requests.get(request)
    return response.json()

def get_current_validator_set_timestamp():
    request = f"{rpc_endpoint}/layer/bridge/get_current_validator_set_timestamp"
    response = requests.get(request)
    return response.json()

def get_validator_set_index_by_timestamp(timestamp):
    request = f"{rpc_endpoint}/layer/bridge/get_validator_set_index_by_timestamp/{timestamp}"
    response = requests.get(request)
    return response.json()

# oracle data functions 
def get_data_before(query_id, timestamp_before):
    query_id = strip_0x(query_id)
    request = f"{rpc_endpoint}/tellor-io/layer/oracle/get_data_before/{query_id}/{timestamp_before}"
    response = requests.get(request)
    return response.json()

def get_snapshots_by_report(query_id, timestamp):
    query_id = strip_0x(query_id)
    request = f"{rpc_endpoint}/layer/bridge/get_snapshots_by_report/{query_id}/{timestamp}"
    response = requests.get(request)
    return response.json()

def get_attestations_by_snapshot(snapshot):
    request = f"{rpc_endpoint}/layer/bridge/get_attestations_by_snapshot/{snapshot}"
    response = requests.get(request)
    return response.json()

def get_attestation_data_by_snapshot(snapshot):
    request = f"{rpc_endpoint}/layer/bridge/get_attestation_data_by_snapshot/{snapshot}"
    response = requests.get(request)
    return response.json()

## queries

def query_latest_oracle_data(query_id):
    # subtract 1 second to account attestation time,
    # TODO: optimize
    current_time = int(time.time()) * 1000 - 1000 
    report = get_data_before(query_id, current_time)
    snapshots = get_snapshots_by_report(query_id, report["timestamp"])
    last_snapshot = snapshots["snapshots"][-1]
    attestations = get_attestations_by_snapshot(last_snapshot)
    attestation_data = get_attestation_data_by_snapshot(last_snapshot)
    current_validator_set = get_current_validator_set()
    oracle_proof = {
        "attestations": attestations,
        "attestation_data": attestation_data,
        "validator_set": current_validator_set,
        "snapshot": last_snapshot
    }
    return oracle_proof

def get_next_validator_set_timestamp(given_timestamp):
    given_ts_index = get_validator_set_index_by_timestamp(given_timestamp).get("index")
    next_ts_index = str(int(given_ts_index) + 1)
    next_ts = get_validator_timestamp_by_index(next_ts_index).get("timestamp")
    return next_ts

def get_previous_validator_set_timestamp(given_timestamp):
    given_ts_index = get_validator_set_index_by_timestamp(given_timestamp).get("index")
    previous_ts_index = str(int(given_ts_index) - 1)
    previous_ts = get_validator_timestamp_by_index(previous_ts_index).get("timestamp")
    return previous_ts

def query_validator_set_update(given_timestamp):
    valset_sigs = get_valset_sigs(given_timestamp)
    valset_checkpoint = get_validator_checkpoint_params(given_timestamp)
    previous_timestamp = get_previous_validator_set_timestamp(given_timestamp)
    previous_valset = get_valset_by_timestamp(previous_timestamp)
    valset_update_params = {
        "valset_sigs": valset_sigs,
        "valset_checkpoint": valset_checkpoint,
        "previous_valset": previous_valset
    }
    return valset_update_params

def get_blobstream_init_params():
    first_timestamp = get_validator_timestamp_by_index(0).get("timestamp")
    checkpoint_params = get_validator_checkpoint_params(first_timestamp)
    return checkpoint_params

def get_layer_latest_validator_timestamp():
    return get_current_validator_set_timestamp().get("timestamp")

def get_current_validator_set():
    latest_timestamp = get_layer_latest_validator_timestamp()
    return get_valset_by_timestamp(latest_timestamp)

