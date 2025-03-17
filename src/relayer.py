from src.layer_client import query_validator_set_update, query_latest_oracle_data, get_blobstream_init_params, get_layer_latest_validator_timestamp, get_next_validator_set_timestamp, get_layer_chain_status, get_blobstream_reset_params, query_latest_oracle_data
from src.evm_client import EVMClient  # Only import the class
from src.transformer import transform_blobstream_init_params, transform_valset_update_params, transform_oracle_update_params, transform_blobstream_reset_params
from src.email_client import send_email_alert
import time
import os

VALSET_SLEEP_TIME = 60

def get_oracle_data(query_id):
    """
    Get oracle data for a specific query ID from tellor chain
    and transform it for the EVM contract
    
    Args:
        query_id: The query ID to get data for
    
    Returns:
        tuple: (oracle_data, error)
    """
    print(f"relayer: Getting oracle data for query ID {query_id}")
    
    # Get oracle data from Layer chain
    oracle_data_response, error = query_latest_oracle_data(query_id)
    if error:
        return None, f"Failed to get oracle data: {error}"
    
    # Transform oracle data for EVM contract
    oracle_update_params = transform_oracle_update_params(oracle_data_response)
    
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
    
    print(f"relayer: Updating oracle data for query ID {query_id} using {contract_type} contract...")
    
    # Initialize EVM client
    evm = EVMClient()
    evm.init_web3()
    
    # Get oracle data
    oracle_data, error = get_oracle_data(query_id)
    if error:
        print(f"relayer: Error getting oracle data: {error}")
        return None, error
    
    # Update oracle data using the appropriate contract
    result = evm.update_oracle_data(oracle_data, contract_type, user_data)
    if isinstance(result, tuple) and len(result) == 2:
        tx_hash, e = result
        if e:
            print("relayer: Error updating oracle data: ", e)
            return None, e
    else:
        print("relayer: Unexpected result from update_oracle_data: ", result)
        return None, "Failed to update oracle data"
    
    return tx_hash, None

def start_relayer():
    """Start the relayer process"""
    query_id = os.getenv("QUERY_ID")
    sleep_time = int(os.getenv("SLEEP_TIME", "600"))
    contract_type = os.getenv("CONTRACT_TYPE", "SimpleLayerUser")
    
    print(f"relayer: Starting relayer for query ID {query_id} using {contract_type} contract...")
    print(f"relayer: Sleep time: {sleep_time} seconds")

    evm = EVMClient()
    evm.init_web3()
    evm.setup_blobstream_contract()
    
    while True:
        try:
            # Check layer chain status
            chain_status, error = get_layer_chain_status()
            if chain_status:
                print(f"relayer: Layer chain status: {chain_status}")
                sleep(sleep_time)
                continue

            # Valset update
            e = handle_validator_set_update(evm)
            if e:
                print(f"relayer: Error handling validator set update: {e}")
                sleep(sleep_time)
                continue
            
            # Update oracle data
            begin_relay_timestamp = int(time.time())
            user_data = {"begin_relay_timestamp": begin_relay_timestamp}
            
            tx_hash, error = update_user_oracle_data(query_id, contract_type, user_data)
            if error:
                print(f"relayer: Error updating oracle data: {error}")
                sleep(sleep_time)
                continue
            
            
        except Exception as e:
            print(f"relayer: Unexpected error: {e}")
        
        sleep(sleep_time)

def blobstream_init(evm) -> Exception:
    print("relayer: Initializing Blobstream...")
    checkpoint_params, e = get_blobstream_init_params()
    if e:
        return e
    print("relayer: Checkpoint params: ", checkpoint_params)
    init_tx_params = transform_blobstream_init_params(checkpoint_params)
    print("relayer: Init tx params: ", init_tx_params)
    init_tx = evm.init_blobstream(init_tx_params)  # Use evm instance method
    print("relayer: Init tx: ", init_tx)
    return None

def blobstream_reset(evm) -> Exception:
    print("relayer: Resetting Blobstream...")
    checkpoint_params, e = get_blobstream_reset_params()
    if e:
        return e
    print("relayer: Checkpoint params: ", checkpoint_params)
    reset_tx_params = transform_blobstream_reset_params(checkpoint_params)
    print("relayer: Reset tx params: ", reset_tx_params)
    evm.reset_blobstream(reset_tx_params)  # Use evm instance method
    return None

def update_to_latest_layer_validator_set(evm, blobstream_validator_timestamp, layer_validator_timestamp) -> Exception:
    while int(blobstream_validator_timestamp) < int(layer_validator_timestamp):
        next_validator_timestamp, e = get_next_validator_set_timestamp(blobstream_validator_timestamp)
        if e:
            return e
        valset_update_params, e = query_validator_set_update(next_validator_timestamp)
        if e:
            return e
        print("relayer: Valset update params: ", valset_update_params)
        valset_update_tx_params = transform_valset_update_params(valset_update_params)
        print("relayer: Valset update tx params: ", valset_update_tx_params)
        valset_update_tx = evm.update_validator_set(valset_update_tx_params)  # Use evm instance method
        sleep(VALSET_SLEEP_TIME)
        layer_validator_timestamp, e = get_layer_latest_validator_timestamp()
        if e:
            return e
        blobstream_validator_timestamp = evm.get_blobstream_validator_timestamp()
        print("relayer: Blobstream validator timestamp: ", blobstream_validator_timestamp)

    print("relayer: Blobstream valset up to date with Layer valset")
    return None

def update_user_oracle_data_2(evm, query_id) -> Exception:
    print("relayer: Updating oracle data...")
    oracle_proof, e = query_latest_oracle_data(query_id)
    if e:
        return e
    current_price_data_timestamp = evm.get_current_price_data_timestamp()  # Use evm instance method
    print("relayer: Current price data timestamp: ", current_price_data_timestamp)
    print("relayer: Oracle proof: ", oracle_proof)
    if int(oracle_proof["attestation_data"]["timestamp"]) > int(current_price_data_timestamp):
        print("relayer: New oracle data available, updating...")
        
    return None

def check_layer_chain_status() -> Exception:
    if os.getenv("EMAIL_PASSWORD") is None:
        return None
    message, e = get_layer_chain_status()
    if message is not None:
        print("relayer: Layer chain status message: ", message)
        e = send_email_alert("Layer chain status alert", message)
        if e:
            return e
    return None

def handle_validator_set_update(evm) -> Exception:
    layer_validator_timestamp, e = get_layer_latest_validator_timestamp()
    if e:
        print("relayer: Error getting latest Layer validator timestamp: ", e)
        return e
    print("relayer: Layer validator timestamp: ", layer_validator_timestamp)
    blobstream_validator_timestamp = evm.get_blobstream_validator_timestamp()
    print("relayer: Blobstream validator timestamp: ", blobstream_validator_timestamp)
    if int(blobstream_validator_timestamp) < int(layer_validator_timestamp):
        print("relayer: Updating to latest Layer validator set...")
        e = update_to_latest_layer_validator_set(evm, blobstream_validator_timestamp, layer_validator_timestamp)
        if e:
            print("relayer: Error updating to latest Layer validator set: ", e)
            return e

def sleep(seconds):
    print("relayer: Sleeping for ", seconds, " seconds")
    time.sleep(seconds)
    return None
