# transformer.py
from web3 import Web3
from evm_client import get_web3_instance
from eth_account.messages import encode_defunct
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
    print("Transforming valset update params...")
    derived_signatures = derive_signatures(valset_update_params["valset_sigs"]["signatures"], valset_update_params["previous_valset"]["bridge_validator_set"], valset_update_params["valset_checkpoint"]["checkpoint"])
    print("Derived signatures: ", derived_signatures)
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

def derive_signatures(signatures, addresses, checkpoint):
    derived_signatures = []
    web3_instance = get_web3_instance()
    data = Web3.to_bytes(hexstr=checkpoint)
    message_hash = sha256(data).digest()
    print("Message hash hex: ", message_hash.hex())
    # message_hash_enc = encode_defunct(primitive=message_hash)
    for i in range(len(signatures)):
        signature = signatures[i]
        address = addresses[i]["ethereumAddress"]
        if len(signature) == 128:
            r = "0x" + signature[:64]
            s = "0x" + signature[64:128]
            for v in [27, 28]:
                print("Recovering address for v: ", v)
                recovered_address = ecrecover_raw_message(message_hash, v, r, s)
                print("Recovered address: ", recovered_address)
                print("Address: ", address)
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
    # Convert the message to bytes if it's a hex string
    if isinstance(message, str) and message.startswith('0x'):
        message = decode_hex(message)
    
    # Convert r and s to bytes if they are hex strings
    if isinstance(r, str) and r.startswith('0x'):
        r = decode_hex(r)
    if isinstance(s, str) and s.startswith('0x'):
        s = decode_hex(s)
    
    # Adjust v value to be compatible with eth_keys library
    if v in (27, 28):
        v -= 27
    
    # Create a signature object
    signature = keys.Signature(vrs=(v, int.from_bytes(r, byteorder='big'), int.from_bytes(s, byteorder='big')))
    
    # Recover the public key from the signature and message
    public_key = signature.recover_public_key_from_msg_hash(message)
    
    # Get the address from the public key
    address = public_key.to_checksum_address()
    
    return address


message_hash = "0xe0665a5193e323fdea2ecd226db9b60417065d8c612bffcd9560143358f7162b"
v = 27
r = "0x24cacaf9a8b333d3e526fe1ccc7919ced129cfb45ef1df15d545fc539afd9501"
s = "0x788d378c88c2983bcdd55b2c8a46a83fba6df0b272cbf378de4c9cd5409ab9c0"

recovered_address = ecrecover_raw_message(message_hash, v, r, s)
print("Recovered address: ", recovered_address)

# checkpoint:  0xff0cd54fa3c8d14b1820162a3b0b586069bd05334026959f6273bbff57b44d9e
# messageHash:  0xe0665a5193e323fdea2ecd226db9b60417065d8c612bffcd9560143358f7162b
# valset:  [
#   {
#     addr: '0x84b918dC8e1E414F39C0A532c0bcA2Df2ACB297C',
#     power: '1000000'
#   }
# ]
# sigs:  [
#   {
#     v: 27,
#     r: '0x24cacaf9a8b333d3e526fe1ccc7919ced129cfb45ef1df15d545fc539afd9501',
#     s: '0x788d378c88c2983bcdd55b2c8a46a83fba6df0b272cbf378de4c9cd5409ab9c0'
#   }
# ]