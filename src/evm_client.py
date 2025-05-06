from web3 import Web3, Account
from web3.types import HexBytes
import json
import os
from dotenv import load_dotenv
import time
from src.contract_adapters import get_contract_adapter

load_dotenv()

class EVMClient:
    def __init__(self):
        self.web3_instance = None
        self.web3_acct = None
        self.blobstream_contract = None
        self.layer_user_contract = None
        self.token_bridge_contract = None
        # self.layer_test_user_contract = None

    def init_web3(self):
        provider_url = os.getenv("WEB3_PROVIDER_URL")
        private_key = os.getenv("ETH_PRIVATE_KEY")
        
        # setup provider
        self.web3_instance = Web3(Web3.HTTPProvider(provider_url))
        # set private key
        self.web3_instance.eth.account.enable_unaudited_hdwallet_features()
        self.web3_acct = Account.from_key(private_key)
        self.web3_instance.eth.defaultAccount = self.web3_acct.address
        
        print("evm_client: Connected to Ethereum node: ", self.web3_instance.is_connected())
        print("evm_client: Using network: ", self.web3_instance.eth.chain_id)
        print("evm_client: Using address: ", self.web3_instance.eth.defaultAccount)
        print("evm_client: Current block number: ", self.web3_instance.eth.block_number)

    def setup_blobstream_contract(self):
        blobstream_address = os.getenv("BLOBSTREAM_CONTRACT_ADDRESS")
        with open("abis/BlobstreamOTestnet.json") as f:
            abi = json.load(f)["abi"]
        self.blobstream_contract = self.web3_instance.eth.contract(address=blobstream_address, abi=abi)
        print("evm_client: Blobstream contract: ", self.blobstream_contract.address)

    def setup_layer_user_contract(self):
        layer_user_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
        with open("abis/SimpleLayerUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        print("evm_client: Layer user contract: ", self.layer_user_contract.address)

    def setup_token_bridge_contract(self):
        token_bridge_address = os.getenv("TOKEN_BRIDGE_CONTRACT_ADDRESS")
        with open("abis/TokenBridge.json") as f:
            abi = json.load(f)["abi"]
        self.token_bridge_contract = self.web3_instance.eth.contract(address=token_bridge_address, abi=abi)
        print("evm_client: Token bridge contract: ", self.token_bridge_contract.address)

    def setup_layer_test_user_contract(self):
        layer_user_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
        with open("abis/TestPriceFeedUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        print("evm_client: Layer user contract: ", self.layer_user_contract.address)

    def setup_yolo_tellor_user_contract(self):
        layer_user_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
        with open("abis/YoloTellorUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        print("evm_client: Layer user contract: ", self.layer_user_contract.address)

    def get_web3_instance(self):
        return self.web3_instance

    def get_blobstream_validator_timestamp(self):
        if not self.blobstream_contract:
            raise Exception("Blobstream contract not initialized")
        return self.blobstream_contract.functions.validatorTimestamp().call()

    def get_current_price_data_timestamp(self):
        print("evm_client: Getting current price data...")
        value_count = self.layer_user_contract.functions.getValueCount().call()
        if value_count == 0:
            return 0
        price_data = self.layer_user_contract.functions.getCurrentPriceData().call()
        timestamp = price_data[1] # timestamp
        return timestamp

    def init_blobstream(self, init_tx_params):
        print("evm_client: Initializing Blobstream...")
        print("evm_client: Init tx params: ", init_tx_params)
        try:
            # Build the transaction
            tx = self.blobstream_contract.functions.init(
                init_tx_params["power_threshold"], 
                init_tx_params["validator_timestamp"], 
                init_tx_params["unbonding_period"], 
                init_tx_params["validator_set_checkpoint"]
            ).build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 300000,
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            })

            print("evm_client: Tx: ", tx)

            # Sign the transaction
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            print("evm_client: Signed transaction: ", signed_tx)

            # Send the transaction
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            print("evm_client: Tx hash: ", tx_hash.hex())
            return tx_hash
        except Exception as e:
            print("evm_client: Error initializing Blobstream: ", e)
            return None
 
    def read_deployer_address(self):
        print("evm_client: Reading deployer address...")
        deployer_address = self.blobstream_contract.functions.deployer().call()
        print("evm_client: Deployer address: ", deployer_address)
        return deployer_address

    def update_validator_set(self, update_tx_params):
        print("evm_client: Updating validator set...")
        print("evm_client: Update tx params: ", update_tx_params)
        try:
            tx = self.blobstream_contract.functions.updateValidatorSet(
                update_tx_params["new_validator_set_hash"],
                update_tx_params["new_power_threshold"],
                update_tx_params["new_validator_timestamp"],
                update_tx_params["current_validator_set"],
                update_tx_params["sigs"]
            ).build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 2000000,  
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            })
            print("evm_client: Tx: ", tx)
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            print("evm_client: Tx hash: ", tx_hash.hex())
            return tx_hash
        except Exception as e:
            print("evm_client: Error updating validator set: ", e)
            return None

    def update_oracle_data(self, oracle_update_params, contract_type="SimpleLayerUser", user_data=None):
        """Update oracle data in the appropriate contract"""
        try:
            contract_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
            if not contract_address:
                return None, "LAYER_USER_CONTRACT_ADDRESS not set"
            
            # Get the appropriate contract based on type
            if contract_type == "SimpleLayerUser":
                if not self.layer_user_contract:
                    self.setup_layer_user_contract()
                contract = self.layer_user_contract
            elif contract_type == "TestPriceFeedUser":
                if not self.layer_user_contract:
                    self.setup_layer_test_user_contract()
                contract = self.layer_user_contract
            elif contract_type == "YoloTellorUser":
                if not self.layer_user_contract:
                    self.setup_yolo_tellor_user_contract()
                contract = self.layer_user_contract
            else:
                return None, f"Unsupported contract type: {contract_type}"
            
            # Get the appropriate adapter
            adapter = get_contract_adapter(contract_type)
            if not adapter:
                return None, f"No adapter found for contract type: {contract_type}"
            
            # Prepare parameters and build transaction
            if user_data is None:
                user_data = {"begin_relay_timestamp": int(time.time())}
            
            params = adapter.prepare_update_params(oracle_update_params, user_data)
            
            # Build and send transaction
            contract_function = adapter.update_oracle_data(contract, params)
            tx = contract_function.build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 1000000,
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25)
            })
            
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"evm_client: Oracle data update tx hash: {tx_hash.hex()}")
            return tx_hash, None
        except Exception as e:
            print(f"evm_client: Error updating oracle data: {e}")
            return None, str(e)

    def reset_blobstream(self, reset_tx_params):
        print("evm_client: Resetting Blobstream...")
        print("evm_client: Reset tx params: ", reset_tx_params)
        try:
            tx = self.blobstream_contract.functions.guardianResetValidatorSet(
                reset_tx_params["power_threshold"],
                reset_tx_params["validator_timestamp"],
                reset_tx_params["validator_set_checkpoint"]
            ).build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 300000,
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            })
            print("evm_client: Tx: ", tx)
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            print("evm_client: Tx hash: ", tx_hash.hex())
            return tx_hash
        except Exception as e:
            print("evm_client: Error resetting Blobstream: ", e)
            return None

    def reset_blobstream_testnet(self, reset_tx_params):
        print("evm_client: Resetting Blobstream...")
        print("evm_client: Reset tx params: ", reset_tx_params)
        try:
            tx = self.blobstream_contract.functions.guardianResetValidatorSetTestnet(
                reset_tx_params["power_threshold"],
                reset_tx_params["validator_timestamp"],
                reset_tx_params["validator_set_checkpoint"]
            ).build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 300000,
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            })
            print("evm_client: Tx: ", tx)
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            print("evm_client: Tx hash: ", tx_hash.hex())
            return tx_hash
        except Exception as e:
            print("evm_client: Error resetting Blobstream: ", e)
            return None
    
    def withdraw_from_layer(self, params: dict):
        if not self.token_bridge_contract:
            raise Exception("Token bridge contract not initialized")
        tx = self.token_bridge_contract.functions.withdrawFromLayer(
            params['oracle_attestation_data'],
            params['current_validator_set'],
            params['sigs'],
            params['withdraw_id']
        ).build_transaction({
            'from': self.web3_acct.address,
            'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
            'gas': 500000,
            'gasPrice': int(self.web3_instance.eth.gas_price * 1.25)
        })
        signed_tx = self.web3_instance.eth.account.sign_transaction(tx, self.web3_acct.key)
        tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash

    def get_withdraw_claimed_status(self, withdraw_id: int) -> bool:
        if not self.token_bridge_contract:
            raise Exception("Token bridge contract not initialized")
        return self.token_bridge_contract.functions.withdrawClaimed(withdraw_id).call()