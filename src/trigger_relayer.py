from threshold_trigger import check_price_change
from layer_client import get_current_aggregate_report, assemble_oracle_data_proof
from transformer import transform_oracle_update_params
from evm_client import update_oracle_data, init_web3, get_blobstream_validator_timestamp, init_blobstream
from relayer import blobstream_init
import time

QUERY_ID = "0x83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992"
QUERY_DATA = "0x00000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000080000000000000000000000000000000000000000000000000000000000000000953706f745072696365000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000003657468000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000037573640000000000000000000000000000000000000000000000000000000000"
ASSET_STRING = "ethereum"
PRICE_THRESHOLD = 0.0001
INTERVAL = 5

class Trigger:
    def __init__(self, trigger_time: int, relay_time: int, relay_tx_hash: str):
        self.trigger_time = trigger_time
        self.relay_time = relay_time
        self.relay_tx_hash = relay_tx_hash

triggers = []

def trigger_relayer():
    print("trigger_relayer: starting relayer")

    print("trigger_relayer: initializing web3")
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
        time.sleep(INTERVAL)
        # todo: update valset
        threshold_met, err = check_price_change(ASSET_STRING, PRICE_THRESHOLD)
        if err:
            print(f"trigger_relayer: error: {err}")
            continue
        if not threshold_met:
            print("trigger_relayer: threshold not met")
            # continue
        print("\n\ntrigger_relayer: threshold met\n\n")
        triggers.append(Trigger(trigger_time=time.time(), relay_time=0, relay_tx_hash=""))

        # tip

        # get tipped report proof
        proof, err = get_tipped_report_proof(QUERY_ID, triggers[-1].trigger_time)
        print("trigger_relayer: proof: ", proof)
        if err:
            print(f"trigger_relayer: error: {err}")
            continue
        oracle_update_tx_params = transform_oracle_update_params(proof)
        print("trigger_relayer: oracle update tx params: ", oracle_update_tx_params)
        tx_hash, err = update_oracle_data(oracle_update_tx_params)
        if err:
            print(f"trigger_relayer: error: {err}")
            continue
        requests[-1].relay_tx_hash = tx_hash

        # update oracle data
        
        # relay



# for reference:
def check_price_change_periodically(currency: str):
    while True:
        threshold_met, err = check_price_change(currency, THRESHOLD)
        if err:
            print(f"threshold_trigger: error: {err}")
            continue
        if threshold_met:
            print("\n\nthreshold_trigger: threshold met\n\n")
            continue
        time.sleep(INTERVAL)

# get tipped report pseudocode:
# query latest oracle data until find report with timestamp > trigger_time
# then query attestations until sufficient attestation power
# then relay

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

def update_validator_set() -> Exception:
    layer_validator_timestamp, err = get_layer_latest_validator_timestamp()
    if err:
        return None, err
    blobstream_validator_timestamp = get_blobstream_validator_timestamp()
    if blobstream_validator_timestamp == 0:
        return None, Exception("blobstream validator timestamp is 0")
    if int(blobstream_validator_timestamp) < int(layer_validator_timestamp):
        return None, Exception("blobstream validator timestamp is less than layer validator timestamp")
    return None
    


trigger_relayer()

