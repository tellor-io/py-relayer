from web3 import Web3, Account
import json
import os
from dotenv import load_dotenv
import time
from src.contract_adapters import get_contract_adapter
from src.logger_utils import get_logger

logger = get_logger(__name__)

load_dotenv()

class EVMClient:
    def __init__(self):
        self.web3_instance = None
        self.web3_acct = None
        self.data_bridge_contract = None
        self.layer_user_contract = None
        self.token_bridge_contract = None
        # self.layer_test_user_contract = None

    def wait_for_transaction_receipt_and_log(self, tx_hash, operation_name, timeout=300):
        """
        Wait for transaction receipt and log success/failure.
        Returns (success: bool, receipt: dict or None)
        """
        try:
            logger.info(f"Waiting for {operation_name} transaction receipt: {tx_hash.hex()}")
            receipt = self.web3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            
            if receipt.status == 1:
                logger.info(f"{operation_name} transaction successful! Block: {receipt.blockNumber}, Gas used: {receipt.gasUsed}")
                return True, receipt
            else:
                logger.error(f"{operation_name} transaction FAILED! Tx hash: {tx_hash.hex()}, Block: {receipt.blockNumber}")
                return False, receipt
                
        except Exception as e:
            logger.error(f"Error waiting for {operation_name} transaction receipt: {e}")
            return False, None

    def init_web3(self):
        provider_url = os.getenv("WEB3_PROVIDER_URL")
        private_key = os.getenv("ETH_PRIVATE_KEY")
        
        # setup provider
        self.web3_instance = Web3(Web3.HTTPProvider(provider_url))
        # set private key
        self.web3_instance.eth.account.enable_unaudited_hdwallet_features()
        self.web3_acct = Account.from_key(private_key)
        self.web3_instance.eth.defaultAccount = self.web3_acct.address
        
        logger.info(f"Connected to Ethereum node: {self.web3_instance.is_connected()}")
        logger.info(f"Using network: {self.web3_instance.eth.chain_id}")
        logger.info(f"Using address: {self.web3_instance.eth.defaultAccount}")
        logger.info(f"Current block number: {self.web3_instance.eth.block_number}")

    def setup_data_bridge_contract(self):
        data_bridge_address = os.getenv("DATA_BRIDGE_CONTRACT_ADDRESS")
        with open("abis/TellorDataBridgeTestnet.json") as f:
            abi = json.load(f)["abi"]
        self.data_bridge_contract = self.web3_instance.eth.contract(address=data_bridge_address, abi=abi)
        logger.info(f"Data bridge contract: {self.data_bridge_contract.address}")

    def setup_layer_user_contract(self):
        layer_user_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
        with open("abis/SimpleLayerUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Layer user contract: {self.layer_user_contract.address}")

    def setup_token_bridge_contract(self):
        token_bridge_address = os.getenv("TOKEN_BRIDGE_CONTRACT_ADDRESS")
        with open("abis/TokenBridge.json") as f:
            abi = json.load(f)["abi"]
        self.token_bridge_contract = self.web3_instance.eth.contract(address=token_bridge_address, abi=abi)
        logger.info(f"Token bridge contract: {self.token_bridge_contract.address}")

    def setup_layer_test_user_contract(self):
        layer_user_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
        with open("abis/TestPriceFeedUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Layer user contract: {self.layer_user_contract.address}")

    def setup_yolo_tellor_user_contract(self):
        layer_user_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
        with open("abis/YoloTellorUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Layer user contract: {self.layer_user_contract.address}")

    def setup_tellor_data_bank_contract(self):
        layer_user_address = os.getenv("LAYER_USER_CONTRACT_ADDRESS")
        with open("abis/TellorDataBank.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Tellor data bank contract: {self.layer_user_contract.address}")

    def get_web3_instance(self):
        return self.web3_instance

    def get_data_bridge_validator_timestamp(self):
        if not self.data_bridge_contract:
            raise Exception("Data bridge contract not initialized")
        return self.data_bridge_contract.functions.validatorTimestamp().call()

    def get_current_price_data_timestamp(self):
        logger.info("Getting current price data...")
        value_count = self.layer_user_contract.functions.getValueCount().call()
        if value_count == 0:
            return 0
        price_data = self.layer_user_contract.functions.getCurrentPriceData().call()
        timestamp = price_data[1] # timestamp
        return timestamp

    def init_data_bridge(self, init_tx_params):
        logger.info("Initializing Data bridge...")
        logger.info(f"Init tx params: {init_tx_params}")
        try:
            # Build the transaction
            tx = self.data_bridge_contract.functions.init(
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

            logger.info(f"Tx: {tx}")

            # Sign the transaction
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            logger.debug(f"Signed transaction: {signed_tx}")

            # Send the transaction
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"Tx hash: {tx_hash.hex()}")
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, "Data bridge initialization")
            if not success:
                return None
                
            return tx_hash
        except Exception as e:
            logger.error(f"Error initializing Data bridge: {e}")
            return None
 
    def read_deployer_address(self):
        logger.info("Reading deployer address...")
        deployer_address = self.data_bridge_contract.functions.deployer().call()
        logger.info(f"Deployer address: {deployer_address}")
        return deployer_address

    def update_validator_set(self, update_tx_params):
        logger.info("Updating validator set...")
        logger.info(f"Update tx params: {update_tx_params}")
        try:
            tx = self.data_bridge_contract.functions.updateValidatorSet(
                update_tx_params["new_validator_set_hash"],
                update_tx_params["new_power_threshold"],
                update_tx_params["new_validator_timestamp"],
                update_tx_params["current_validator_set"],
                update_tx_params["sigs"]
            ).build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 1000000,  
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            })
            logger.info(f"Tx: {tx}")
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"Tx hash: {tx_hash.hex()}")
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, "Validator set update")
            if not success:
                return None
                
            return tx_hash
        except Exception as e:
            logger.error(f"Error updating validator set: {e}")
            return None

    def update_oracle_data(self, oracle_update_params, contract_type="SimpleLayerUser", user_data=None) -> tuple[str, str]:
        """
        Update oracle data in the appropriate contract
        Returns (tx_hash: str, error: str)
        """
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
            elif contract_type == "TellorDataBank":
                if not self.layer_user_contract:
                    self.setup_tellor_data_bank_contract()
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
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, f"Oracle data update ({contract_type})")
            if not success:
                return None, "Transaction failed"
                
            return tx_hash, None
        except Exception as e:
            logger.error(f"Error updating oracle data: {e}")
            return None, str(e)

    def reset_data_bridge(self, reset_tx_params):
        logger.info("Resetting Data bridge...")
        logger.info(f"Reset tx params: {reset_tx_params}")
        try:
            tx = self.data_bridge_contract.functions.guardianResetValidatorSet(
                reset_tx_params["power_threshold"],
                reset_tx_params["validator_timestamp"],
                reset_tx_params["validator_set_checkpoint"]
            ).build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 300000,
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            })
            logger.info(f"Tx: {tx}")
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"Tx hash: {tx_hash.hex()}")
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, "Data bridge reset")
            if not success:
                return None
                
            return tx_hash
        except Exception as e:
            logger.error(f"Error resetting Data bridge: {e}")
            return None

    def reset_data_bridge_testnet(self, reset_tx_params):
        logger.info("Resetting Data bridge...")
        logger.info(f"Reset tx params: {reset_tx_params}")
        try:
            tx = self.data_bridge_contract.functions.guardianResetValidatorSetTestnet(
                reset_tx_params["power_threshold"],
                reset_tx_params["validator_timestamp"],
                reset_tx_params["validator_set_checkpoint"]
            ).build_transaction({
                'from': self.web3_acct.address,
                'nonce': self.web3_instance.eth.get_transaction_count(self.web3_acct.address),
                'gas': 300000,
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            })
            logger.info(f"Tx: {tx}")
            signed_tx = self.web3_instance.eth.account.sign_transaction(tx, private_key=self.web3_acct.key)
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"Tx hash: {tx_hash.hex()}")
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, "Data bridge testnet reset")
            if not success:
                return None
                
            return tx_hash
        except Exception as e:
            logger.error(f"Error resetting TellorDataBridge: {e}")
            return None
    
    def withdraw_from_layer(self, params: dict):
        if not self.token_bridge_contract:
            raise Exception("Token bridge contract not initialized")
        try:
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
            logger.info(f"Withdraw tx hash: {tx_hash.hex()}")
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, "Layer withdrawal")
            if not success:
                return None
                
            return tx_hash
        except Exception as e:
            logger.error(f"Error withdrawing from layer: {e}")
            return None

    def get_withdraw_claimed_status(self, withdraw_id: int) -> bool:
        if not self.token_bridge_contract:
            raise Exception("Token bridge contract not initialized")
        return self.token_bridge_contract.functions.withdrawClaimed(withdraw_id).call()

    def get_last_relayed_data(self, contract_type="TellorDataBank"):
        """
        Get the last relayed data from the user contract
        Returns decoded data in a standardized format
        """
        from src.contract_adapters import get_contract_adapter, adapter_can_read_data
        
        if not self.layer_user_contract:
            # Setup appropriate contract based on type
            if contract_type == "TellorDataBank":
                self.setup_tellor_data_bank_contract()
            elif contract_type == "TestPriceFeedUser":
                self.setup_layer_test_user_contract()
            # Add other contract types as needed
        
        adapter = get_contract_adapter(contract_type)
        if not adapter or not adapter_can_read_data(adapter):
            raise Exception(f"Contract type {contract_type} does not support reading data")
        
        query_id = os.getenv("QUERY_ID")
        raw_data = adapter.get_last_relayed_data(self.layer_user_contract, query_id).call()
        return adapter.decode_last_relayed_data(raw_data)