import requests
import time

query_id = "0x83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992" # eth/usd
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
    # http://localhost:1317/tellor-io/layer/oracle/get_data_before/83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992/1721672771868
    query_id = strip_0x(query_id)
    request = f"{rpc_endpoint}/tellor-io/layer/oracle/get_data_before/{query_id}/{timestamp_before}"
    response = requests.get(request)
    return response.json()

def get_snapshots_by_report(query_id, timestamp):
    # "http://localhost:1317/layer/bridge/get_snapshots_by_report/83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992/1721672771868""
    query_id = strip_0x(query_id)
    request = f"{rpc_endpoint}/layer/bridge/get_snapshots_by_report/{query_id}/{timestamp}"
    response = requests.get(request)
    return response.json()

def get_attestations_by_snapshot(snapshot):
    # "http://localhost:1317/layer/bridge/get_attestations_by_snapshot/df077f3d8e8a9f62533289d3bac8b82fd26c9c4cc1d79657463178140cc1ee26"
    request = f"{rpc_endpoint}/layer/bridge/get_attestations_by_snapshot/{snapshot}"
    response = requests.get(request)
    return response.json()

def get_attestation_data_by_snapshot(snapshot):
    # "http://localhost:1317/layer/bridge/get_attestation_data_by_snapshot/df077f3d8e8a9f62533289d3bac8b82fd26c9c4cc1d79657463178140cc1ee26"
    request = f"{rpc_endpoint}/layer/bridge/get_attestation_data_by_snapshot/{snapshot}"
    response = requests.get(request)
    return response.json()


def query_latest_oracle_data(query_id):
    current_time = int(time.time()) * 1000
    report = get_data_before(query_id, current_time)
    snapshots = get_snapshots_by_report(query_id, report["timestamp"])
    last_snapshot = snapshots["snapshots"][-1]
    attestations = get_attestations_by_snapshot(last_snapshot)
    attestation_data = get_attestation_data_by_snapshot(last_snapshot)
    oracle_proof = {
        "report": report,
        "attestations": attestations,
        "attestation_data": attestation_data
    }
    return oracle_proof

def get_next_validator_set_timestamp(given_timestamp):
    given_ts_index = get_validator_set_index_by_timestamp(given_timestamp).get("index")
    next_ts_index = str(int(given_ts_index) + 1)
    next_ts = get_validator_timestamp_by_index(next_ts_index).get("timestamp")
    return next_ts

def query_validator_set_update(last_known_timestamp):
    current_ts = get_current_validator_set_timestamp().get("timestamp")
    if int(current_ts) > int(last_known_timestamp):
        next_ts = get_next_validator_set_timestamp(last_known_timestamp)
        valset_sigs = get_valset_sigs(next_ts)
        valset_checkpoint = get_validator_checkpoint_params(next_ts)
        print("\nvalset_sigs: ", valset_sigs)
        print("\nvalset_checkpoint: ", valset_checkpoint)



# assemble_latest_layer_proof(query_id)

last_known_timestamp = get_validator_timestamp_by_index(0).get("timestamp")
print("\nlast_known_timestamp: ", last_known_timestamp)
query_validator_set_update(last_known_timestamp)