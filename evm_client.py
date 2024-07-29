from web3 import Web3, Account
from web3.types import HexBytes
import json

blobstream_address = "0x447786d977Ea11Ad0600E193b2d07A06EfB53e5F"
layer_user_address = "0x6DcBc91229d812910b54dF91b5c2b592572CD6B0"
provider_url = "http://127.0.0.1:8545"
private_key = "96e9178d78da25aa25aaa2af908dda3c421029e8d8c6cca355c21a50a68c8870"

web3_instance = None
blobstream_contract = None
layer_user_contract = None

def init_web3():
    connect_web3()
    setup_contracts()

def connect_web3():
    # setup provider
    web3 = Web3(Web3.HTTPProvider(provider_url))
    # set private key
    web3.eth.account.enable_unaudited_hdwallet_features()
    acct = Account.from_key(private_key)
    web3.eth.defaultAccount = acct.address
    print("evm_client: Connected to Ethereum node: ", web3.is_connected())
    print("evm_client: Using network: ", "local")
    print("evm_client: Using address: ", web3.eth.defaultAccount)
    print("evm_client: Current block number: ", web3.eth.block_number)
    global web3_instance
    web3_instance = web3

def setup_contracts():
    with open("abis/BlobstreamO.json") as f:
        abi = json.load(f)["abi"]

    global blobstream_contract
    blobstream_contract = web3_instance.eth.contract(address=blobstream_address, abi=abi)

    with open("abis/SimpleLayerUser.json") as f:
        abi = json.load(f)["abi"]

    global layer_user_contract
    layer_user_contract = web3_instance.eth.contract(address=layer_user_address, abi=abi)
    print("evm_client: Layer user contract: ", layer_user_contract.address)
    print("evm_client: Blobstream contract: ", blobstream_contract.address)

def get_web3_instance():
    return web3_instance

def get_blobstream_validator_timestamp():
    print("evm_client: Getting Blobstream validator timestamp...")
    validator_timestamp = blobstream_contract.functions.validatorTimestamp().call()
    return validator_timestamp

def get_current_price_data_timestamp():
    print("evm_client: Getting current price data...")
    price_data = layer_user_contract.functions.getCurrentPriceData().call()
    timestamp = price_data[1] # timestamp
    return timestamp

def init_blobstream(init_tx_params):
    print("evm_client: Initializing Blobstream...")
    print("evm_client: Init tx params: ", init_tx_params)
    try:
        blobstream_contract.functions.init(
            init_tx_params["power_threshold"], 
            init_tx_params["validator_timestamp"], 
            init_tx_params["unbonding_period"], 
            init_tx_params["validator_set_checkpoint"]
        ).transact()
    except Exception as e:
        print("evm_client: Error initializing Blobstream: ", e)
        # raise e 

def update_validator_set(update_tx_params):
    print("evm_client: Updating validator set...")
    print("evm_client: Update tx params: ", update_tx_params)
    try:
        blobstream_contract.functions.updateValidatorSet(
            update_tx_params["new_validator_set_hash"],
            update_tx_params["new_power_threshold"],
            update_tx_params["new_validator_timestamp"],
            update_tx_params["current_validator_set"],
            update_tx_params["sigs"]
        ).transact()
    except Exception as e:
        print("evm_client: Error updating validator set: ", e)
        # raise e

def update_oracle_data(update_tx_params) -> (HexBytes, Exception):
    print("evm_client: Updating oracle data...")
    print("evm_client: Update tx params: ", update_tx_params)
    try:
        tx_hash = layer_user_contract.functions.updateOracleData(
            update_tx_params["oracle_attestation_data"],
            update_tx_params["current_validator_set"],
            update_tx_params["sigs"]
        ).transact()
    except Exception as e:
        print("evm_client: Error updating oracle data: ", e)
        return None, e
    return tx_hash, None