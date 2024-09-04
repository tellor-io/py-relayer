# transformer.py
from web3 import Web3
from hashlib import sha256
from eth_keys import keys
from eth_utils import decode_hex

def transform_blobstream_init_params(checkpoint_params):
    init_params = {
        "power_threshold": int(checkpoint_params.get("power_threshold")),
        "validator_timestamp": int(checkpoint_params.get("timestamp")),
        "unbonding_period": 86400 * 21,
        "validator_set_checkpoint": Web3.to_bytes(hexstr=checkpoint_params.get("checkpoint"))
    }
    return init_params

def transform_valset_update_params(valset_update_params):
    print("transformer: Transforming valset update params...")
    derived_signatures = derive_signatures(valset_update_params["valset_sigs"]["signatures"], valset_update_params["previous_valset"]["bridge_validator_set"], valset_update_params["valset_checkpoint"]["checkpoint"])
    print("transformer: Derived signatures: ", derived_signatures)
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
                "v": int(sig["v"]),
                "r": Web3.to_bytes(hexstr=sig["r"]),
                "s": Web3.to_bytes(hexstr=sig["s"])
            }
            for sig in derived_signatures
        ]
    }
    return update_params

def transform_oracle_update_params(oracle_update_params):
    print("transformer: Transforming oracle update params...")
    attestations = oracle_update_params["attestations"]["attestations"]
    attestation_data = oracle_update_params["attestation_data"]
    validator_set = oracle_update_params["validator_set"]["bridge_validator_set"]
    snapshot = oracle_update_params["snapshot"]
    derived_signatures = derive_signatures(attestations, validator_set, snapshot)
    print("transformer: Derived signatures: ", derived_signatures)
    update_params = {
        "oracle_attestation_data": {
            "queryId": Web3.to_bytes(hexstr=attestation_data["query_id"]),
            "report": {
                "value": Web3.to_bytes(hexstr=attestation_data["aggregate_value"]),
                "timestamp": int(attestation_data["timestamp"]),
                "aggregatePower": int(attestation_data["aggregate_power"]),
                "previousTimestamp": int(attestation_data["previous_report_timestamp"]),
                "nextTimestamp": int(attestation_data["next_report_timestamp"])
            },
            "attestationTimestamp": int(attestation_data["attestation_timestamp"])
        },
        "current_validator_set": [
            {
                "addr": Web3.to_checksum_address(validator["ethereumAddress"]),
                "power": int(validator["power"])
            }
            for validator in validator_set
        ],
        "sigs": [
            {
                "v": int(sig["v"]),
                "r": Web3.to_bytes(hexstr=sig["r"]),
                "s": Web3.to_bytes(hexstr=sig["s"])
            }
            for sig in derived_signatures
        ]
    }
    return update_params

def transform_withdraw_tx_params(withdraw_tx_params, withdraw_id):
    print("transformer: Transforming withdraw tx params...")
    attestations = withdraw_tx_params["attestations"]["attestations"]
    attestation_data = withdraw_tx_params["attestation_data"]
    validator_set = withdraw_tx_params["validator_set"]["bridge_validator_set"]
    snapshot = withdraw_tx_params["snapshot"]
    derived_signatures = derive_signatures(attestations, validator_set, snapshot)
    print("transformer: Derived signatures: ", derived_signatures)
    withdraw_params = {
        "oracle_attestation_data": {
            "queryId": Web3.to_bytes(hexstr=attestation_data["query_id"]),
            "report": {
                "value": Web3.to_bytes(hexstr=attestation_data["aggregate_value"]),
                "timestamp": int(attestation_data["timestamp"]),
                "aggregatePower": int(attestation_data["aggregate_power"]),
                "previousTimestamp": int(attestation_data["previous_report_timestamp"]),
                "nextTimestamp": int(attestation_data["next_report_timestamp"])
            },
            "attestationTimestamp": int(attestation_data["attestation_timestamp"])
        },
        "current_validator_set": [
            {
                "addr": Web3.to_checksum_address(validator["ethereumAddress"]),
                "power": int(validator["power"])
            }
            for validator in validator_set
        ],
        "sigs": [
            {
                "v": int(sig["v"]),
                "r": Web3.to_bytes(hexstr=sig["r"]),
                "s": Web3.to_bytes(hexstr=sig["s"])
            }
            for sig in derived_signatures
        ],
        "withdraw_id": int(withdraw_id)
    }
    return withdraw_params

def derive_signatures(signatures, validator_set, checkpoint):
    derived_signatures = []
    data = Web3.to_bytes(hexstr=checkpoint)
    message_hash = sha256(data).digest()
    for i in range(len(signatures)):
        signature = signatures[i]
        address = validator_set[i]["ethereumAddress"]
        if len(signature) == 128:
            r = "0x" + signature[:64]
            s = "0x" + signature[64:128]
            for v in [27, 28]:
                recovered_address = ecrecover_raw_message(message_hash, v, r, s)
                if recovered_address.lower() == address.lower():
                    derived_signatures.append({
                        "v": v,
                        "r": r,
                        "s": s
                    })
        else:
            derived_signatures.append({
                "v": 0,
                "r": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "s": "0x0000000000000000000000000000000000000000000000000000000000000000"
            })

    return derived_signatures

def ecrecover_raw_message(message, v, r, s):
    # convert message to bytes if hex string
    if isinstance(message, str) and message.startswith('0x'):
        message = decode_hex(message)
    
    # convert r and s to bytes if hex strings
    if isinstance(r, str) and r.startswith('0x'):
        r = decode_hex(r)
    if isinstance(s, str) and s.startswith('0x'):
        s = decode_hex(s)
    
    # adjust v value to be compatible with eth_keys library
    if v in (27, 28):
        v -= 27
    
    # create signature object
    signature = keys.Signature(vrs=(v, int.from_bytes(r, byteorder='big'), int.from_bytes(s, byteorder='big')))
    
    # recover public key from signature and message
    public_key = signature.recover_public_key_from_msg_hash(message)
    
    # get address from public key
    address = public_key.to_checksum_address()
    
    return address
