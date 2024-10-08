from layer_client import query_validator_set_update, query_latest_oracle_data, get_blobstream_init_params, get_layer_latest_validator_timestamp, get_next_validator_set_timestamp, get_layer_chain_status
from evm_client import init_web3, get_blobstream_validator_timestamp, init_blobstream, update_validator_set, get_current_price_data_timestamp, update_oracle_data
from transformer import transform_blobstream_init_params, transform_valset_update_params, transform_oracle_update_params
from email_client import send_email_alert
import time
import os
from dotenv import load_dotenv

load_dotenv()

QUERY_ID = os.getenv("QUERY_ID")
SLEEP_TIME = int(os.getenv("SLEEP_TIME"))
VALSET_SLEEP_TIME = 60

def start_relayer():
    print("relayer: Starting relayer...")

    print("relayer: Initializing web3...")
    init_web3()
    blobstream_validator_timestamp = get_blobstream_validator_timestamp()
    print("relayer: Blobstream validator timestamp: ", blobstream_validator_timestamp)

    if blobstream_validator_timestamp == 0:
        print("relayer: Initializing Blobstream...")
        e = blobstream_init()
        if e:
            print("relayer: Error initializing Blobstream: ", e)
            return

    while True:
        time.sleep(SLEEP_TIME)
        e = check_layer_chain_status()
        if e:
            print("relayer: Error checking layer chain status: ", e)
            continue
        layer_validator_timestamp, e = get_layer_latest_validator_timestamp()
        if e:
            print("relayer: Error getting latest Layer validator timestamp: ", e)
            continue
        print("relayer: Layer validator timestamp: ", layer_validator_timestamp)
        blobstream_validator_timestamp = get_blobstream_validator_timestamp()
        print("relayer: Blobstream validator timestamp: ", blobstream_validator_timestamp)
        if int(blobstream_validator_timestamp) < int(layer_validator_timestamp):
            print("relayer: Updating to latest Layer validator set...")
            e = update_to_latest_layer_validator_set(blobstream_validator_timestamp, layer_validator_timestamp)
            if e:
                print("relayer: Error updating to latest Layer validator set: ", e)
                continue
        e = update_user_oracle_data(QUERY_ID)
        if e:
            print("relayer: Error updating user oracle data: ", e)
            continue

def blobstream_init() -> Exception:
    print("relayer: Initializing Blobstream...")
    checkpoint_params, e = get_blobstream_init_params()
    if e:
        return e
    print("relayer: Checkpoint params: ", checkpoint_params)
    init_tx_params = transform_blobstream_init_params(checkpoint_params)
    print("relayer: Init tx params: ", init_tx_params)
    init_tx = init_blobstream(init_tx_params)
    print("relayer: Init tx: ", init_tx)
    return None

def update_to_latest_layer_validator_set(blobstream_validator_timestamp, layer_validator_timestamp) -> Exception:
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
        valset_update_tx = update_validator_set(valset_update_tx_params)
        print("relayer: Valset update tx: ", valset_update_tx)
        time.sleep(VALSET_SLEEP_TIME)
        layer_validator_timestamp, e = get_layer_latest_validator_timestamp()
        if e:
            return e
        blobstream_validator_timestamp = get_blobstream_validator_timestamp()
        print("relayer: Blobstream validator timestamp: ", blobstream_validator_timestamp)

    print("relayer: Blobstream valset up to date with Layer valset")
    return None

def update_user_oracle_data(query_id) -> Exception:
    print("relayer: Updating oracle data...")
    oracle_proof, e = query_latest_oracle_data(query_id)
    if e:
        return e
    current_price_data_timestamp = get_current_price_data_timestamp()
    print("relayer: Current price data timestamp: ", current_price_data_timestamp)
    print("relayer: Oracle proof: ", oracle_proof)
    if int(oracle_proof["attestation_data"]["timestamp"]) > int(current_price_data_timestamp):
        print("relayer: New oracle data available, updating...")
        oracle_update_tx_params = transform_oracle_update_params(oracle_proof)
        print("relayer: Oracle update tx params: ", oracle_update_tx_params)
        tx_hash, e = update_oracle_data(oracle_update_tx_params)
        if e:
            return e
        print("relayer: Oracle data updated: ", tx_hash.hex())
    else:
        print("relayer: No new oracle data available")
    return None

def check_layer_chain_status() -> Exception:
    # check if email password is set
    if os.getenv("EMAIL_PASSWORD") is None:
        return None
    message, e = get_layer_chain_status()
    if message is not None:
        print("relayer: Layer chain status message: ", message)
        e = send_email_alert("Layer chain status alert", message)
        if e:
            return e
    return None

start_relayer()
