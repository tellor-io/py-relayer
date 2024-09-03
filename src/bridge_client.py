from web3 import Web3
from eth_abi import encode
from layer_client import query_latest_oracle_data, update_oracle_data
from evm_client import get_withdraw_claimed_status
from transformer import transform_oracle_update_params
import time
withdraws_list = []
highest_withdraw_id = 0
withdraw_delay = 43200 # seconds
max_attestation_age = 43200 # seconds

# things to check:
# 	- withdrawal id __exists__
# 	- report timestamp __old enough__
# 	- attestation timestamp __recent enough__
# 	- attestation checkpoint __latest__
def relay_withdraw(withdraw_id):
    withdraw_query_id = get_withdraw_query_id(withdraw_id)
    # check if withdrawal id exists
    oracle_proof, e = query_latest_oracle_data(withdraw_query_id)
    if e:
        return False
    # report old enough
    report_ts = int(oracle_proof["attestation_data"]["timestamp"]) / 1000
    if time.time() - report_ts < withdraw_delay:
        return False
    # attestation recent enough
    attest_ts = int(oracle_proof["attestation_data"]["attestation_timestamp"]) / 1000
    if time.time() - attest_ts > max_attestation_age:
        return False
    
    # check if withdraw is claimed
    claimed, e = get_withdraw_claimed_status(withdraw_id)
    if e:
        return False
    if claimed is True:
        print("bridge_client: Withdraw already claimed")
        return False
    
    oracle_update_tx_params = transform_oracle_update_params(oracle_proof)
    print("bridge_client: Oracle update tx params: ", oracle_update_tx_params)
    tx_hash, e = update_oracle_data(oracle_update_tx_params)
    if e:
        return False
    print("bridge_client: Oracle data updated: ", tx_hash.hex())

def get_list_of_pending_withdraws():
    next_withdraw_id = highest_withdraw_id + 1
    append_list = fill_list_until_error(next_withdraw_id)
    if len(append_list) > 0:
        withdraws_list.extend(append_list)

def fill_list_until_error(next_withdraw_id):
    append_list = []
    fill_bool = True
    while fill_bool is True:
        next_withdraw_query_id = get_withdraw_query_id(next_withdraw_id)
        oracle_data, e = query_latest_oracle_data(next_withdraw_query_id)
        if e:
            return append_list
        withdraw_data = {
            "withdraw_id": next_withdraw_id,
            "oracle_data": oracle_data
        }
        append_list.append(withdraw_data)
        next_withdraw_id += 1

def get_withdraw_query_id(withdraw_id: int) -> str:
    query_data_args = encode(["bool", "uint256"], [False, withdraw_id])
    query_data = encode(["string", "bytes"], ["TRBBridge", query_data_args])
    return Web3.keccak(query_data)

