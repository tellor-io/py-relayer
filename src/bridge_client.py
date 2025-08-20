from web3 import Web3
from eth_abi import encode
from src.layer_client import query_latest_oracle_data, get_layer_connection_status, get_attestation_data_before
from src.evm_client import EVMClient
from src.transformer import transform_withdraw_tx_params
from src.relayer import handle_validator_set_update, get_latest_oracle_proof_from_layer
from src.layer_tx_client import request_attestations
from src.logger_utils import get_logger
import time
import os

logger = get_logger(__name__)

withdraw_delay = 43200 # seconds
max_attestation_age = 43200 # seconds
withdraw_id_to_relay = int(os.getenv("WITHDRAW_ID"))

# things to check:
# 	- withdrawal id __exists__
# 	- report timestamp __old enough__
# 	- attestation timestamp __recent enough__
# 	- attestation checkpoint __latest__
def relay_withdraw(withdraw_id) -> (int, Exception):
    logger.info(f"Relaying withdraw: {withdraw_id}")
    evm = EVMClient()
    evm.init_web3()
    evm.setup_data_bridge_contract()
    evm.setup_token_bridge_contract()
    
    withdraw_query_id = get_withdraw_query_id(withdraw_id)
    logger.info(f"Withdraw query id: {withdraw_query_id}")
    # check if withdrawal id exists
    attest_data, e = get_attestation_data_before(withdraw_query_id, int(time.time()) * 1000)
    if e:
        return None, e
    
    logger.debug(f"Attestation data: {attest_data}")
    
    # report old enough
    report_ts = int(attest_data["timestamp"]) / 1000
    if time.time() - report_ts < withdraw_delay:
        logger.warning("Report too new")
        return None, e
    
    # check if withdraw is claimed
    claimed = evm.get_withdraw_claimed_status(withdraw_id)
    if claimed:
        logger.warning("Withdraw already claimed")
        return 1, None
    
    # get the latest oracle proof, with checkpoint mismatch check
    oracle_proof, e = get_latest_oracle_proof_from_layer(withdraw_query_id)
    if e:
        return None, e
    
    # attestation recent enough
    attest_ts = int(oracle_proof["attestation_data"]["attestation_timestamp"]) / 1000
    if time.time() - attest_ts > max_attestation_age:
        logger.warning("Attestation too old")
        layer_status, e = get_layer_connection_status()
        if e:
            return None, e
        chain_id = layer_status.get("result").get("node_info").get("network")
        # use the original timestamp string, not the converted float
        e = request_attestations(withdraw_query_id, oracle_proof["attestation_data"]["timestamp"], os.getenv("LAYER_ADDRESS"), os.getenv("LAYER_RPC_ENDPOINT"), chain_id)
        # sleep for 5 seconds
        time.sleep(5)
        # get the new oracle proof
        oracle_proof, e = get_latest_oracle_proof_from_layer(withdraw_query_id)
        if e:
            return None, e
        # check if the new oracle proof is recent enough
        attest_ts = int(oracle_proof["attestation_data"]["attestation_timestamp"]) / 1000
        if time.time() - attest_ts > max_attestation_age:
            logger.error("Attestation still too old")
            return None, e
    
    # update validator set
    e = handle_validator_set_update(evm)
    if e:
        logger.error(f"Error updating validator set: {e}")
        return None, e
    
    # assemble the oracle update tx params and relay
    oracle_update_tx_params = transform_withdraw_tx_params(oracle_proof, withdraw_id)
    logger.debug(f"Oracle update tx params: {oracle_update_tx_params}")
    tx_hash = evm.withdraw_from_layer(oracle_update_tx_params)
    if not tx_hash:
        return None, Exception("Failed to withdraw from layer")
    logger.info(f"Oracle data updated: {tx_hash.hex()}")
    return 2, None

def get_withdraw_query_id(withdraw_id: int) -> str:
    query_data_args = encode(["bool", "uint256"], [False, withdraw_id])
    query_data = encode(["string", "bytes"], ["TRBBridge", query_data_args])
    query_id = Web3.keccak(query_data)
    return query_id.hex()