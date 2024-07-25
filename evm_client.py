from web3 import Web3, Account
import json

blobstream_address = "0x5FC8d32690cc91D4c39d9d3abcBD16989F875707"
layer_user_address = "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9"
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
    print("Connected to Ethereum node: ", web3.is_connected())
    print("Using network: ", "local")
    print("Using address: ", web3.eth.defaultAccount)
    print("Current block number: ", web3.eth.block_number)
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
    print("Layer user contract: ", layer_user_contract.address)
    print("Blobstream contract: ", blobstream_contract.address)

def get_web3_instance():
    return web3_instance

# def blobstream_init():

def get_blobstream_validator_timestamp():
    print("Getting Blobstream validator timestamp...")
    validator_timestamp = blobstream_contract.functions.validatorTimestamp().call()
    return validator_timestamp

def init_blobstream(init_tx_params):
    blobstream_contract.functions.init(init_tx_params["power_threshold"], init_tx_params["validator_timestamp"], init_tx_params["unbonding_period"], init_tx_params["validator_set_checkpoint"]).transact()

def update_validator_set(update_tx_params):
    print("Updating validator set...")
    print("Update tx params: ", update_tx_params)
    # blobstream_contract.functions.updateValidatorSet(
    #     update_tx_params["new_validator_set_hash"],
    #     update_tx_params["new_power_threshold"],
    #     update_tx_params["new_validator_timestamp"],
    #     update_tx_params["current_validator_set"],
    #     update_tx_params["sigs"]
    # ).transact()

    print("updateSigs")
    blobstream_contract.functions.updateSigs(update_tx_params["sigs"]).transact()