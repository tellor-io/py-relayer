from layer_client import query_validator_set_update, query_latest_oracle_data, get_validator_timestamp_by_index, get_blobstream_init_params, get_layer_latest_validator_timestamp, get_next_validator_set_timestamp
from evm_client import init_web3, get_blobstream_validator_timestamp, init_blobstream, update_validator_set
from transformer import transform_blobstream_init_params, transform_valset_update_params


blobstream_contract_address = "0x0000000000000000000000000000000000000000"
query_id = "0x83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992" # eth/usd

def start_relayer():
    print("Starting relayer...")

    print("Initializing web3...")
    init_web3()
    blobstream_validator_timestamp = get_blobstream_validator_timestamp()
    print("Blobstream validator timestamp: ", blobstream_validator_timestamp)

    if blobstream_validator_timestamp == 0:
        print("Initializing Blobstream...")
        blobstream_init()
        blobstream_validator_timestamp = get_blobstream_validator_timestamp()

    layer_validator_timestamp = get_layer_latest_validator_timestamp()
    print("Layer validator timestamp: ", layer_validator_timestamp)

    if int(blobstream_validator_timestamp) < int(layer_validator_timestamp):
        print("Updating to latest Layer validator set...")
        update_to_latest_layer_validator_set(blobstream_validator_timestamp, layer_validator_timestamp)


    
    


def blobstream_init():
    print("Initializing Blobstream...")
    checkpoint_params = get_blobstream_init_params()
    print("Checkpoint params: ", checkpoint_params)
    init_tx_params = transform_blobstream_init_params(checkpoint_params)
    print("Init tx params: ", init_tx_params)
    init_tx = init_blobstream(init_tx_params)
    print("Init tx: ", init_tx)

    

def update_to_latest_layer_validator_set(blobstream_validator_timestamp, layer_validator_timestamp):
    while int(blobstream_validator_timestamp) < int(layer_validator_timestamp):
        next_validator_timestamp = get_next_validator_set_timestamp(blobstream_validator_timestamp)
        valset_update_params = query_validator_set_update(next_validator_timestamp)
        print("Valset update params: ", valset_update_params)
        valset_update_tx_params = transform_valset_update_params(valset_update_params)
        print("Valset update tx params: ", valset_update_tx_params)
        valset_update_tx = update_validator_set(valset_update_tx_params)
        print("Valset update tx: ", valset_update_tx)
        blobstream_validator_timestamp = get_blobstream_validator_timestamp()
        # print("Blobstream validator timestamp: ", blobstream_validator_timestamp)
    
    print("Blobstream valset up to date with Layer valset")
        

 


start_relayer()
