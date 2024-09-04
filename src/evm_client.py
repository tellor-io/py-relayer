from web3 import Web3, Account
from web3.types import HexBytes
import json
import os
from eth_abi import encode
from dotenv import load_dotenv

load_dotenv()

BLOBSTREAM_ADDRESS = os.getenv("BLOBSTREAM_CONTRACT_ADDRESS")
LAYER_USER_ADDRESS = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
TOKEN_BRIDGE_ADDRESS = os.getenv("TOKEN_BRIDGE_CONTRACT_ADDRESS")
PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL")
PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")

web3_instance = None
blobstream_contract = None
layer_user_contract = None
token_bridge_contract = None
web3_acct = None

def init_web3():
    connect_web3()
    setup_contracts()

def connect_web3():
    # setup provider
    web3 = Web3(Web3.HTTPProvider(PROVIDER_URL))
    # set private key
    web3.eth.account.enable_unaudited_hdwallet_features()
    acct = Account.from_key(PRIVATE_KEY)
    web3.eth.defaultAccount = acct.address
    print("evm_client: Connected to Ethereum node: ", web3.is_connected())
    print("evm_client: Using network: ", web3.eth.chain_id)
    print("evm_client: Using address: ", web3.eth.defaultAccount)
    print("evm_client: Current block number: ", web3.eth.block_number)
    global web3_instance
    web3_instance = web3
    global web3_acct
    web3_acct = acct

def setup_contracts():
    with open("abis/BlobstreamO.json") as f:
        abi = json.load(f)["abi"]

    global blobstream_contract
    blobstream_contract = web3_instance.eth.contract(address=BLOBSTREAM_ADDRESS, abi=abi)

    with open("abis/SimpleLayerUser.json") as f:
        abi = json.load(f)["abi"]

    global layer_user_contract
    layer_user_contract = web3_instance.eth.contract(address=LAYER_USER_ADDRESS, abi=abi)

    global token_bridge_contract
    with open("abis/TokenBridge.json") as f:
        abi = json.load(f)["abi"]
    token_bridge_contract = web3_instance.eth.contract(address=TOKEN_BRIDGE_ADDRESS, abi=abi)
    print("evm_client: Layer user contract: ", layer_user_contract.address)
    print("evm_client: Blobstream contract: ", blobstream_contract.address)
    print("evm_client: Token bridge contract: ", token_bridge_contract.address)

def get_web3_instance():
    return web3_instance

def get_blobstream_validator_timestamp():
    print("evm_client: Getting Blobstream validator timestamp...")
    validator_timestamp = blobstream_contract.functions.validatorTimestamp().call()
    return validator_timestamp

def get_current_price_data_timestamp():
    print("evm_client: Getting current price data...")
    value_count = layer_user_contract.functions.getValueCount().call()
    if value_count == 0:
        return 0
    price_data = layer_user_contract.functions.getCurrentPriceData().call()
    timestamp = price_data[1] # timestamp
    return timestamp

def init_blobstream(init_tx_params):
    print("evm_client: Initializing Blobstream...")
    print("evm_client: Init tx params: ", init_tx_params)
    try:
        # Build the transaction
        tx = blobstream_contract.functions.init(
            init_tx_params["power_threshold"], 
            init_tx_params["validator_timestamp"], 
            init_tx_params["unbonding_period"], 
            init_tx_params["validator_set_checkpoint"]
        ).build_transaction({
            'from': web3_acct.address,
            'nonce': web3_instance.eth.get_transaction_count(web3_acct.address),
            'gas': 300000,
            'gasPrice': web3_instance.eth.gas_price,
        })

        print("evm_client: Tx: ", tx)

        # Sign the transaction
        signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        print("evm_client: Signed transaction: ", signed_tx)

        # Send the transaction
        tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        print("evm_client: Tx hash: ", tx_hash)
        return tx_hash
    except Exception as e:
        print("evm_client: Error initializing Blobstream: ", e)
        return None
 
def read_deployer_address():
    print("evm_client: Reading deployer address...")
    deployer_address = blobstream_contract.functions.deployer().call()
    print("evm_client: Deployer address: ", deployer_address)
    return deployer_address

def update_validator_set(update_tx_params):
    print("evm_client: Updating validator set...")
    print("evm_client: Update tx params: ", update_tx_params)
    try:
        tx = blobstream_contract.functions.updateValidatorSet(
            update_tx_params["new_validator_set_hash"],
            update_tx_params["new_power_threshold"],
            update_tx_params["new_validator_timestamp"],
            update_tx_params["current_validator_set"],
            update_tx_params["sigs"]
        ).build_transaction({
            'from': web3_acct.address,
            'nonce': web3_instance.eth.get_transaction_count(web3_acct.address),
            'gas': 2000000,  
            'gasPrice': web3_instance.eth.gas_price,
        })
        print("evm_client: Tx: ", tx)
        signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        print("evm_client: Tx hash: ", tx_hash)
        return tx_hash
    except Exception as e:
        print("evm_client: Error updating validator set: ", e)
        return None

def update_oracle_data(update_tx_params) -> (HexBytes, Exception):
    print("evm_client: Updating oracle data...")
    print("evm_client: Update tx params: ", update_tx_params)
    try:
        tx = layer_user_contract.functions.updateOracleData(
            update_tx_params["oracle_attestation_data"],
            update_tx_params["current_validator_set"],
            update_tx_params["sigs"]
        ).build_transaction({
            'from': web3_acct.address,
            'nonce': web3_instance.eth.get_transaction_count(web3_acct.address),
            'gas': 2000000,  
            'gasPrice': web3_instance.eth.gas_price,
        })
        print("evm_client: Tx: ", tx)
        signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        print("evm_client: Tx hash: ", tx_hash.hex())
        return tx_hash, None
    except Exception as e:
        print("evm_client: Error updating oracle data: ", e)
        return None, e

def withdraw_from_layer(withdraw_tx_params) -> (HexBytes, Exception):
    print("evm_client: Withdrawing from layer...")
    print("evm_client: Withdraw tx params: ", withdraw_tx_params)
    try:
        tx = token_bridge_contract.functions.withdrawFromLayer(
            withdraw_tx_params["oracle_attestation_data"],
            withdraw_tx_params["current_validator_set"],
            withdraw_tx_params["sigs"],
            withdraw_tx_params["deposit_id"]
        ).build_transaction({
            'from': web3_acct.address,
            'nonce': web3_instance.eth.get_transaction_count(web3_acct.address),
            'gas': 2000000,  
            'gasPrice': web3_instance.eth.gas_price,
        })
        print("evm_client: Tx: ", tx)
        signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        print("evm_client: Tx hash: ", tx_hash.hex())
        return tx_hash, None
    except Exception as e:
        print("evm_client: Error withdrawing from layer: ", e)
        return None, e

def get_withdraw_claimed_status(withdraw_id: int) -> (bool, Exception):
    print("evm_client: Getting withdraw claimed status...")
    print("evm_client: Withdraw id: ", withdraw_id)
    try:
        claimed = token_bridge_contract.functions.withdrawClaimed(withdraw_id).call()
        print("evm_client: Withdraw claimed status: ", claimed)
        return claimed, None
    except Exception as e:
        print("evm_client: Error getting withdraw claimed status: ", e)
        return False, e