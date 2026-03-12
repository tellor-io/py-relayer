from web3 import Web3, Account
import json
import os
from dotenv import load_dotenv
import time
import random
from typing import Callable, Optional, Tuple
from src.contract_adapters import get_contract_adapter
from src.logger_utils import get_logger
from src.evm_rpc import EvmRpcResolver

logger = get_logger(__name__)

load_dotenv()

def is_nonce_error(error) -> bool:
    """
    Check if an error is a nonce/sequence conflict that can be retried.
    
    Args:
        error: Exception or error object to check
    
    Returns:
        bool: True if this is a nonce conflict that should be retried
    """
    error_str = str(error).lower()
    nonce_error_patterns = [
        'invalid nonce',
        'nonce too low',
        'nonce too high', 
        'invalid sequence',
        'replacement transaction underpriced',
        'already known'
    ]
    
    return any(pattern in error_str for pattern in nonce_error_patterns)

def is_rate_limit_error(error) -> bool:
    """
    Detect if an error is due to provider rate limiting.
    """
    error_str = str(error).lower()
    return "429" in error_str or "too many requests" in error_str or "rate limit" in error_str

def send_transaction_with_retry(
    web3_instance,
    web3_acct,
    contract_function,
    base_tx_params,
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
    jitter=True,
    refresh_web3_callback: Optional[Callable[[], Tuple]] = None,
):
    """
    Send a transaction with exponential backoff retry logic for nonce conflicts.
    
    Args:
        web3_instance: Web3 instance
        web3_acct: Web3 account object
        contract_function: Contract function to call
        base_tx_params: Base transaction parameters (without nonce)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay between retries
        jitter: Whether to add random jitter to prevent thundering herd
    
    Returns:
        tuple: (tx_hash, Exception) - tx_hash on success, Exception on failure
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Get fresh nonce for each attempt
            current_nonce = web3_instance.eth.get_transaction_count(web3_acct.address)
            
            # Build transaction with fresh nonce
            tx_params = base_tx_params.copy()
            tx_params['nonce'] = current_nonce
            
            logger.debug(f"Transaction attempt {attempt + 1}/{max_retries + 1} with nonce {current_nonce}")
            
            tx = contract_function.build_transaction(tx_params)
            signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=web3_acct.key)
            tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f"Transaction submitted successfully on attempt {attempt + 1} with nonce {current_nonce}")
            return tx_hash, None
            
        except Exception as e:
            last_error = e
            logger.warning(f"Transaction attempt {attempt + 1} failed: {e}")
            
            # Check if this is a nonce error that we should retry
            if is_nonce_error(e):
                # If this was our last attempt, don't sleep
                if attempt >= max_retries:
                    break
                    
                # Calculate exponential backoff delay
                delay = min(base_delay * (2 ** attempt), max_delay)
                
                # Add jitter to prevent thundering herd problem
                if jitter:
                    delay += random.uniform(0, delay * 0.1)  # Add up to 10% jitter
                
                logger.info(f"Nonce conflict detected, retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                continue

            # For provider rate limits / HTTP errors, try to refresh RPC and retry
            if is_rate_limit_error(e) and refresh_web3_callback and attempt < max_retries:
                logger.warning(f"Rate limit or provider error detected, refreshing RPC and retrying: {e}")
                try:
                    web3_instance, web3_acct = refresh_web3_callback()
                except Exception as refresh_err:
                    logger.error(f"Failed to refresh web3 provider after rate limit: {refresh_err}")
                    return None, Exception(f"Transaction failed with non-retryable error: {e}")
                # small backoff before retrying new provider
                delay = min(base_delay * (2 ** attempt), max_delay)
                if jitter:
                    delay += random.uniform(0, delay * 0.1)
                logger.info(f"Retrying with refreshed provider in {delay:.2f} seconds...")
                time.sleep(delay)
                continue

            logger.error(f"Non-retryable error encountered: {e}")
            return None, Exception(f"Transaction failed with non-retryable error: {e}")
    
    # All retries exhausted
    logger.error(f"Transaction failed after {max_retries + 1} attempts. Last error: {last_error}")
    return None, Exception(f"Transaction failed after {max_retries + 1} attempts: {last_error}")

class EVMClient:
    def __init__(self):
        self.web3_instance = None
        self.web3_acct = None
        self.data_bridge_contract = None
        self.layer_user_contract = None
        self.token_bridge_contract = None
        # self.layer_test_user_contract = None
        self._evm_resolver = None
        self._evm_network = None

    def wait_for_transaction_receipt_and_log(self, tx_hash, operation_name, timeout=300):
        """
        Wait for transaction receipt and log success/failure.
        Returns (success: bool, receipt: dict or None)
        """
        try:
            logger.info(f"Waiting for {operation_name} transaction receipt: {tx_hash.hex()}")
            self._refresh_web3_if_needed()
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
        evm_network = os.getenv("EVM_NETWORK")
        
        # setup provider (direct URL) or via resolver (network)
        if provider_url:
            self.web3_instance = Web3(Web3.HTTPProvider(provider_url))
        elif evm_network:
            self._evm_network = evm_network
            self._evm_resolver = EvmRpcResolver(os.environ.get("EVM_NETWORKS_CONFIG"))
            self.web3_instance = self._evm_resolver.get_web3(evm_network)
        else:
            raise Exception("Must set WEB3_PROVIDER_URL or EVM_NETWORK")
        # set private key
        self.web3_instance.eth.account.enable_unaudited_hdwallet_features()
        self.web3_acct = Account.from_key(private_key)
        # web3.py v6 uses default_account instead of defaultAccount
        self.web3_instance.eth.default_account = self.web3_acct.address
        # ensure we are on a healthy provider (switch if rate limited)
        self._ensure_chain_connection()
        
        logger.info(f"Connected to Ethereum node: {self.web3_instance.is_connected()}")
        logger.info(f"Using network: {self.web3_instance.eth.chain_id}")
        logger.info(f"Using address: {self.web3_instance.eth.default_account}")
        logger.info(f"Current block number: {self.web3_instance.eth.block_number}")

    def _refresh_web3_if_needed(self):
        if self._evm_resolver and self._evm_network:
            try:
                self.web3_instance = self._evm_resolver.get_web3(self._evm_network)
            except Exception:
                # keep existing instance; send will fail and upstream logic will handle
                pass

    def _refresh_web3_with_account(self):
        """
        Refresh the web3 provider (switches RPC if current is unhealthy) and return updated (web3, account).
        """
        self._refresh_web3_if_needed()
        return self.web3_instance, self.web3_acct

    def _ensure_chain_connection(self):
        """
        Ensure the current web3 instance can respond (e.g., not rate-limited).
        Tries once and refreshes provider on failure.
        """
        for attempt in range(2):
            try:
                # simple health call; eth.chain_id is lightweight
                _ = self.web3_instance.eth.chain_id
                return
            except Exception as e:
                logger.warning(f"Web3 health check failed (attempt {attempt + 1}): {e}")
                self._refresh_web3_if_needed()
        raise Exception("Unable to establish healthy EVM RPC connection")

    def setup_data_bridge_contract(self):
        self._refresh_web3_if_needed()
        data_bridge_address = os.getenv("DATA_BRIDGE_ADDRESS")
        with open("abis/TellorDataBridgeTestnet.json") as f:
            abi = json.load(f)["abi"]
        self.data_bridge_contract = self.web3_instance.eth.contract(address=data_bridge_address, abi=abi)
        logger.info(f"Data bridge contract: {self.data_bridge_contract.address}")

    def setup_layer_user_contract(self):
        self._refresh_web3_if_needed()
        layer_user_address = os.getenv("LAYER_USER_ADDRESS")
        with open("abis/SimpleLayerUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Layer user contract: {self.layer_user_contract.address}")

    def setup_token_bridge_contract(self):
        self._refresh_web3_if_needed()
        token_bridge_address = os.getenv("TOKEN_BRIDGE_ADDRESS")
        with open("abis/TokenBridge.json") as f:
            abi = json.load(f)["abi"]
        self.token_bridge_contract = self.web3_instance.eth.contract(address=token_bridge_address, abi=abi)
        logger.info(f"Token bridge contract: {self.token_bridge_contract.address}")

    def setup_layer_test_user_contract(self):
        self._refresh_web3_if_needed()
        layer_user_address = os.getenv("LAYER_USER_ADDRESS")
        with open("abis/TestPriceFeedUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Layer user contract: {self.layer_user_contract.address}")

    def setup_yolo_tellor_user_contract(self):
        self._refresh_web3_if_needed()
        layer_user_address = os.getenv("LAYER_USER_ADDRESS")
        with open("abis/YoloTellorUser.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Layer user contract: {self.layer_user_contract.address}")

    def setup_tellor_data_bank_contract(self):
        self._refresh_web3_if_needed()
        layer_user_address = os.getenv("LAYER_USER_ADDRESS")
        with open("abis/TellorDataBank.json") as f:
            abi = json.load(f)["abi"]
        self.layer_user_contract = self.web3_instance.eth.contract(address=layer_user_address, abi=abi)
        logger.info(f"Tellor data bank contract: {self.layer_user_contract.address}")

    def get_web3_instance(self):
        self._refresh_web3_if_needed()
        return self.web3_instance

    def get_data_bridge_validator_timestamp(self):
        if not self.data_bridge_contract:
            raise Exception("Data bridge contract not initialized")
        self._refresh_web3_if_needed()
        return self.data_bridge_contract.functions.validatorTimestamp().call()

    def get_current_price_data_timestamp(self):
        logger.info("Getting current price data...")
        self._refresh_web3_if_needed()
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
            self._refresh_web3_if_needed()
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
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
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
        self._refresh_web3_if_needed()
        deployer_address = self.data_bridge_contract.functions.deployer().call()
        logger.info(f"Deployer address: {deployer_address}")
        return deployer_address

    def update_validator_set(self, update_tx_params) -> tuple[str, Exception]:
        """
        Update the validator set
        Returns (tx_hash: str, error: Exception)
        """
        logger.info("Updating validator set...")
        logger.info(f"Update tx params: {update_tx_params}")
        try:
            self._refresh_web3_if_needed()
            contract_function = self.data_bridge_contract.functions.updateValidatorSet(
                update_tx_params["new_validator_set_hash"],
                update_tx_params["new_power_threshold"],
                update_tx_params["new_validator_timestamp"],
                update_tx_params["current_validator_set"],
                update_tx_params["sigs"]
            )
            
            base_tx_params = {
                'from': self.web3_acct.address,
                'gas': 700000,  
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.25),
            }
            
            # Use retry logic for transaction submission
            tx_hash, tx_error = send_transaction_with_retry(
                self.web3_instance, 
                self.web3_acct, 
                contract_function, 
                base_tx_params,
                refresh_web3_callback=self._refresh_web3_with_account,
                max_retries=5,
                base_delay=1.0,
                max_delay=30.0
            )
            
            if tx_error:
                return None, tx_error
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, "Validator set update")
            if not success:
                return None, Exception("Transaction failed")
                
            return tx_hash, None
        except Exception as e:
            logger.error(f"Error updating validator set: {e}")
            return None, Exception(f"Error updating validator set: {e}")

    def update_oracle_data(self, oracle_update_params, contract_type="SimpleLayerUser", user_data=None) -> tuple[str, Exception]:
        """
        Update oracle data in the appropriate contract
        Returns (tx_hash: str, error: Exception)
        """
        try:
            self._refresh_web3_if_needed()
            contract_address = os.getenv("LAYER_USER_ADDRESS")
            if not contract_address:
                return None, Exception("LAYER_USER_ADDRESS not set")
            
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
                return None, Exception(f"Unsupported contract type: {contract_type}")
            
            # Get the appropriate adapter
            adapter = get_contract_adapter(contract_type)
            if not adapter:
                return None, Exception(f"No adapter found for contract type: {contract_type}")
            
            # Prepare parameters and build transaction
            if user_data is None:
                user_data = {"begin_relay_timestamp": int(time.time())}
            
            params = adapter.prepare_update_params(oracle_update_params, user_data)
            
            # Build and send transaction with retry logic
            contract_function = adapter.update_oracle_data(contract, params)
            base_tx_params = {
                'from': self.web3_acct.address,
                'gas': 800000,
                'gasPrice': int(self.web3_instance.eth.gas_price * 1.5)
            }
            
            # Use retry logic for transaction submission
            tx_hash, tx_error = send_transaction_with_retry(
                self.web3_instance, 
                self.web3_acct, 
                contract_function, 
                base_tx_params,
                refresh_web3_callback=self._refresh_web3_with_account,
                max_retries=5,  # configurable
                base_delay=1.0,  # start with 1 second
                max_delay=30.0   # max 30 seconds between retries
            )
            
            if tx_error:
                return None, tx_error
            
            # Wait for receipt and check success
            success, _ = self.wait_for_transaction_receipt_and_log(tx_hash, f"Oracle data update ({contract_type})")
            if not success:
                return None, Exception("Transaction failed")
                
            return tx_hash, None
        except Exception as e:
            logger.error(f"Error updating oracle data: {e}")
            return None, Exception(f"Error updating oracle data: {e}")

    def reset_data_bridge(self, reset_tx_params):
        logger.info("Resetting Data bridge...")
        logger.info(f"Reset tx params: {reset_tx_params}")
        try:
            self._refresh_web3_if_needed()
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
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
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
            self._refresh_web3_if_needed()
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
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
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
            self._refresh_web3_if_needed()
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
            tx_hash = self.web3_instance.eth.send_raw_transaction(signed_tx.raw_transaction)
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
        self._refresh_web3_if_needed()
        return self.token_bridge_contract.functions.withdrawClaimed(withdraw_id).call()

    def get_last_relayed_data(self, contract_type="TellorDataBank") -> tuple[dict, Exception]:
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
            return None, Exception(f"Contract type {contract_type} does not support reading data")
        
        self._refresh_web3_if_needed()
        query_id = os.getenv("QUERY_ID")
        raw_data = adapter.get_last_relayed_data(self.layer_user_contract, query_id).call()
        return adapter.decode_last_relayed_data(raw_data), None