# transformer.py
from web3 import Web3

def transform_blobstream_init_params(checkpoint_params):
    init_params = {
        "power_threshold": int(checkpoint_params.get("power_threshold")),
        "validator_timestamp": int(checkpoint_params.get("timestamp")),
        "unbonding_period": 86400 * 21,
        "validator_set_checkpoint": Web3.to_bytes(hexstr=checkpoint_params.get("checkpoint"))
    }
    return init_params

def transform_valset_update_params(valset_update_params):
    print("Transforming valset update params...")
    update_params = {
        "new_validator_set_hash": Web3.to_bytes(hexstr=valset_update_params["valset_checkpoint"]["valset_hash"]),
        "new_power_threshold": int(valset_update_params["valset_checkpoint"]["power_threshold"]),
        "new_validator_timestamp": int(valset_update_params["valset_checkpoint"]["timestamp"]),
        "current_validator_set": [
            {
            
                "addr": Web3.to_checksum_address(validator["ethereumAddress"]),
                "power": int(validator["power"])
            }
            for validator in valset_update_params["previous_valset"]["bridge_validator_set"]
        ],
        "sigs": [
            {
                "v": int(sig[:2], 16),
                "r": Web3.to_bytes(hexstr=sig[2:66]),
                "s": Web3.to_bytes(hexstr=sig[66:])
            }
            for sig in valset_update_params["valset_sigs"]["signatures"]
        ]
    }
    return update_params