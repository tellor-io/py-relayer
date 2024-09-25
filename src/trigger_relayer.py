from threshold_trigger import check_price_change
from layer_client import get_current_aggregate_report, assemble_oracle_data_proof
from transformer import transform_oracle_update_params
from evm_client import update_oracle_data, init_web3, get_blobstream_validator_timestamp, init_blobstream
from layer_tipper import tip
from relayer import blobstream_init, handle_validator_set_update, initialize_blobstream
import time
from dotenv import load_dotenv
import os
load_dotenv()

QUERY_ID = os.getenv("QUERY_ID")
QUERY_DATA = os.getenv("QUERY_DATA")
ASSET_STRING_COINGECKO = os.getenv("ASSET_STRING_COINGECKO")
PRICE_THRESHOLD = os.getenv("PRICE_THRESHOLD")
INTERVAL = 5

class Trigger:
    def __init__(self, trigger_time: int, relay_time: int, relay_tx_hash: str):
        self.trigger_time = trigger_time
        self.relay_time = relay_time
        self.relay_tx_hash = relay_tx_hash
        self.tip_tx_hash = tip_tx_hash
triggers = []

def trigger_relayer():
    print("trigger_relayer: starting relayer")

    print("trigger_relayer: initializing web3")
    init_web3()
    e = initialize_blobstream()
    if e:
        print("trigger_relayer: Error initializing Blobstream: ", e)
        return

    while True:
        time.sleep(INTERVAL)
        e = handle_validator_set_update()
        if e:
            print("trigger_relayer: Error handling validator set update: ", e)
            continue
        threshold_met, err = check_price_change(ASSET_STRING_COINGECKO, PRICE_THRESHOLD)
        if err:
            print(f"trigger_relayer: error: {err}")
            continue
        if not threshold_met:
            print("trigger_relayer: threshold not met")
            # continue
        print("\n\ntrigger_relayer: threshold met\n\n")
        triggers.append(Trigger(trigger_time=time.time(), relay_time=0, relay_tx_hash="", tip_tx_hash=""))

        # tip
        tx_hash, err = tip()
        if err:
            print(f"trigger_relayer: error: {err}")
            continue
        triggers[-1].tip_tx_hash = tx_hash

        # get tipped report proof
        proof, err = get_tipped_report_proof(QUERY_ID, triggers[-1].trigger_time)
        print("trigger_relayer: proof: ", proof)
        if err:
            print(f"trigger_relayer: error: {err}")
            continue

        # transform oracle update tx params
        oracle_update_tx_params = transform_oracle_update_params(proof)
        print("trigger_relayer: oracle update tx params: ", oracle_update_tx_params)

        # update oracle data
        tx_hash, err = update_oracle_data(oracle_update_tx_params)
        if err:
            print(f"trigger_relayer: error: {err}")
            continue


def get_tipped_report_timestamp(query_id: str, trigger_time: int) -> tuple[dict, Exception]:
    print("trigger_relayer: getting tipped report timestamp")
    report_found = False
    while not report_found:
        report, err = get_current_aggregate_report(query_id)
        if err:
            return None, err
        if not report["timestamp"]:
            return None, Exception("no timestamp")
        if int(report["timestamp"]) > trigger_time:
            return report["timestamp"], None
        time.sleep(1)
    
def get_tipped_report_proof(query_id: str, trigger_time: int) -> tuple[dict, Exception]:
    print("trigger_relayer: getting tipped report proof")
    timestamp, err = get_tipped_report_timestamp(query_id, trigger_time)
    if err:
        return None, err
    proof, err = assemble_oracle_data_proof(query_id, timestamp)
    if err:
        return None, err
    return proof, None

trigger_relayer()

