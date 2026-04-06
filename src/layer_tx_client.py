from src.layer_client import strip_0x, get_minimum_gas_prices, get_oracle_module_params, get_layer_chain_id
from src.logger_utils import get_logger
import subprocess
import time
import random
import json

logger = get_logger(__name__)
__minimum_gas_prices = "0loya"
__minimum_tip_amount = "0loya"

def is_sequence_error(error_output) -> bool:
    """
    Check if an error is a sequence/nonce conflict that can be retried.
    
    Args:
        error_output: String containing the error output from layerd command
    
    Returns:
        bool: True if this is a sequence conflict that should be retried
    """
    if not error_output:
        return False
        
    error_str = str(error_output).lower()
    sequence_error_patterns = [
        'sequence mismatch',
        'account sequence mismatch', 
        'incorrect account sequence',
    ]
    
    return any(pattern in error_str for pattern in sequence_error_patterns)

def get_account_sequence(layer_address, layer_rpc_endpoint, chain_id="layertest-5"):
    """
    Get the current sequence number for an account.
    
    Args:
        layer_address: The Layer address to query
        layer_rpc_endpoint: The Layer RPC endpoint
        chain_id: The chain ID
    
    Returns:
        tuple: (sequence_number, error) - sequence number on success, error on failure
    """
    try:
        # Use the auth module to query account information
        result = subprocess.run(
            ["layerd", "query", "auth", "account", layer_address,
             "--chain-id", chain_id,
             "--node=" + layer_rpc_endpoint,
             "--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )

        account_data = json.loads(result.stdout)
        sequence = int(account_data.get("account", {}).get("value", {}).get("sequence", 0))
        logger.debug(f"Current sequence for {layer_address}: {sequence}")
        return sequence, None
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting account sequence: {e.stderr}")
        return None, Exception(f"Failed to get account sequence: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error getting account sequence: {e}")
        return None, Exception(f"Unexpected error getting account sequence: {e}")

def verify_layer_transaction(txhash, layer_rpc_endpoint, chain_id, retries=5, poll_delay=3.0):
    """
    Poll the node until a broadcasted transaction is found and check its result code.

    Returns:
        tuple: (success: bool, error: Exception or None)
            success=True only when the tx is found on-chain with code 0.
    """
    for attempt in range(retries):
        time.sleep(poll_delay)
        try:
            result = subprocess.run(
                ["layerd", "query", "tx", txhash,
                 "--node=" + layer_rpc_endpoint,
                 "--output", "json"],
                capture_output=True,
                text=True,
            )
            raw = result.stdout.strip()
            logger.debug(f"Tx query stdout: {raw}")
            if result.stderr.strip():
                logger.debug(f"Tx query stderr: {result.stderr.strip()}")

            if not raw:
                logger.info(f"Tx {txhash} not yet found on attempt {attempt + 1}/{retries}, retrying...")
                continue

            tx_data = json.loads(raw)
            code = tx_data.get("code", 0)
            raw_log = tx_data.get("raw_log", "")
            height = tx_data.get("height", "?")

            if code == 0:
                logger.info(f"Tx {txhash} confirmed on-chain at height {height}")
                return True, None
            else:
                logger.error(f"Tx {txhash} included at height {height} but FAILED with code {code}: {raw_log}")
                return False, Exception(f"Transaction on-chain failure (code {code}): {raw_log}")

        except json.JSONDecodeError:
            logger.debug(f"Non-JSON response for tx query (attempt {attempt + 1}): {result.stdout[:200]}")
        except Exception as e:
            logger.debug(f"Error querying tx {txhash} (attempt {attempt + 1}): {e}")

    logger.warning(f"Tx {txhash} not confirmed after {retries} poll attempts — it may still be pending or was dropped")
    return False, Exception(f"Transaction {txhash} not found on-chain after {retries} attempts")


def send_layer_transaction_with_sequence_retry(command_args, operation_name, layer_address, 
                                             layer_rpc_endpoint, chain_id="layertest-5",
                                             max_retries=5, base_delay=1.0, max_delay=60.0, jitter=True):
    """
    Send a Layer transaction with sequence-aware retry logic.
    This version explicitly manages sequence numbers to avoid conflicts.
    
    Args:
        command_args: List of command arguments for layerd
        operation_name: Name of the operation for logging
        layer_address: The Layer address to use
        layer_rpc_endpoint: The Layer RPC endpoint
        chain_id: The chain ID
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay between retries
        jitter: Whether to add random jitter to prevent thundering herd
    
    Returns:
        tuple: (success: bool, result: subprocess.CompletedProcess or None, error: Exception or None)
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Get current sequence number before each attempt
            current_sequence, seq_error = get_account_sequence(layer_address, layer_rpc_endpoint, chain_id)
            if seq_error:
                logger.warning(f"Could not get sequence number for attempt {attempt + 1}: {seq_error}")
                # Continue without explicit sequence management
            
            logger.debug(f"Layer transaction attempt {attempt + 1}/{max_retries + 1} for {operation_name}")
            if current_sequence is not None:
                logger.debug(f"Current sequence: {current_sequence}")
            
            result = subprocess.run(
                command_args,
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"layerd stdout: {result.stdout}")
            if result.stderr.strip():
                logger.debug(f"layerd stderr: {result.stderr.strip()}")

            txhash = result.stdout.split("txhash: ")[1].split("\n")[0].strip()
            logger.info(f"Transaction broadcast for {operation_name} on attempt {attempt + 1}. Txhash: {txhash}")

            confirmed, verify_error = verify_layer_transaction(txhash, layer_rpc_endpoint, chain_id)
            if confirmed:
                logger.info(f"Layer transaction confirmed on-chain for {operation_name}. Txhash: {txhash}")
                return True, result, None
            else:
                logger.error(f"Layer transaction not confirmed for {operation_name}: {verify_error}")
                return False, None, verify_error
            
        except subprocess.CalledProcessError as e:
            last_error = e
            error_output = e.stderr or e.stdout or str(e)
            logger.warning(f"Layer transaction attempt {attempt + 1} failed for {operation_name}: {error_output}")
            
            # Check if this is a sequence error that we should retry
            if not is_sequence_error(error_output):
                logger.error(f"Non-retryable error encountered for {operation_name}: {error_output}")
                return False, None, Exception(f"Transaction failed with non-retryable error: {error_output}")
            
            # If this was our last attempt, don't sleep
            if attempt >= max_retries:
                break
                
            # Calculate exponential backoff delay
            delay = min(base_delay * (2 ** attempt), max_delay)
            
            # Add jitter to prevent thundering herd problem
            if jitter:
                delay += random.uniform(0, delay * 0.1)  # Add up to 10% jitter
            
            logger.info(f"Sequence conflict detected for {operation_name}, retrying in {delay:.2f} seconds...")
            time.sleep(delay)
    
    # All retries exhausted
    logger.error(f"Layer transaction failed after {max_retries + 1} attempts for {operation_name}. Last error: {last_error}")
    return False, None, Exception(f"Transaction failed after {max_retries + 1} attempts: {last_error}")

def tip(query_data, layer_address, layer_rpc_endpoint, chain_id=None) -> Exception:
    """
    Tip for oracle data with retry logic for sequence conflicts.
    
    Args:
        query_data: The query data to tip for
        layer_address: The Layer address to use
        layer_rpc_endpoint: The Layer RPC endpoint
        chain_id: The chain ID (auto-detected from the node when not provided)
    
    Returns:
        Exception: None on success, Exception on failure
    """
    # ensure all parameters are strings for subprocess
    # remove 0x prefix if it exists
    query_data_stripped = strip_0x(str(query_data))
    layer_address_str = str(layer_address)
    layer_rpc_endpoint_str = str(layer_rpc_endpoint)

    if not chain_id:
        detected_chain_id, e = get_layer_chain_id()
        if e or not detected_chain_id:
            logger.warning(f"Could not auto-detect chain ID: {e}. Falling back to layertest-5")
            detected_chain_id = "layertest-5"
        chain_id_str = detected_chain_id
        logger.info(f"Auto-detected chain ID: {chain_id_str}")
    else:
        chain_id_str = str(chain_id)
    gas_price = minimum_gas_prices()
    min_tip_amount = minimum_tip_amount()

    logger.debug(f"Tipping {min_tip_amount} for query {query_data_stripped}")
    logger.debug(f"Layer address: {layer_address_str}  Chain ID: {chain_id_str} Layer RPC Endpoint: {layer_rpc_endpoint_str}")
    
    # Build the command arguments
    command_args = [
        "layerd", "tx", "oracle", "tip",
        query_data_stripped,
        min_tip_amount, 
        "--from", layer_address_str, 
        "--chain-id", chain_id_str,
        "--gas=auto",
        "--gas-adjustment=1.5",
        "--gas-prices", gas_price,
        "--keyring-backend", "test", 
        "--yes", 
        "--node=" + layer_rpc_endpoint_str
    ]
    
    # Use sequence-aware retry logic for transaction submission
    success, _, error = send_layer_transaction_with_sequence_retry(
        command_args, 
        "oracle tip",
        layer_address_str,
        layer_rpc_endpoint_str,
        chain_id_str,
        max_retries=5,
        base_delay=1.0,
        max_delay=30.0
    )
    
    if not success:
        logger.error(f"Failed to tip after retries: {error}")
        return error
    
    return None

def request_attestations(query_id, timestamp, layer_address, layer_rpc_endpoint, chain_id="layertest-5") -> Exception:
    """
    Request attestations with retry logic for sequence conflicts.
    
    Args:
        query_id: The query ID to request attestations for
        timestamp: The timestamp for the request
        layer_address: The Layer address to use
        layer_rpc_endpoint: The Layer RPC endpoint
        chain_id: The chain ID
    
    Returns:
        Exception: None on success, Exception on failure
    """
    # ensure all parameters are strings for subprocess
    # remove 0x prefix if it exists
    query_id_str = strip_0x(str(query_id))
    timestamp_str = str(timestamp)
    layer_address_str = str(layer_address)
    layer_rpc_endpoint_str = str(layer_rpc_endpoint)
    chain_id_str = str(chain_id)
    gas_price = minimum_gas_prices()
    
    logger.debug(f"Requesting attestations for query {query_id_str} at timestamp {timestamp_str}")
    logger.debug(f"Layer address: {layer_address_str}  Chain ID: {chain_id_str} Layer RPC Endpoint: {layer_rpc_endpoint_str}")
    
    # Build the command arguments
    command_args = [
        "layerd", "tx", "bridge", "request-attestations",
        layer_address_str,
        query_id_str,
        timestamp_str,
        "--from", layer_address_str,
        "--chain-id", chain_id_str,
        "--gas=auto",
        "--gas-adjustment=1.5",
        "--gas-prices", gas_price,
        "--keyring-backend", "test",
        "--yes",
        "--node=" + layer_rpc_endpoint_str
    ]
    
    # Use sequence-aware retry logic for transaction submission
    success, _, error = send_layer_transaction_with_sequence_retry(
        command_args, 
        "request attestations",
        layer_address_str,
        layer_rpc_endpoint_str,
        chain_id_str,
        max_retries=5,
        base_delay=1.0,
        max_delay=30.0
    )
    
    if not success:
        logger.error(f"Failed to request attestations after retries: {error}")
        return error
    
    return None

def minimum_gas_prices():
    global __minimum_gas_prices
    if __minimum_gas_prices == "0loya":
        __minimum_gas_prices, error = get_minimum_gas_prices()
        if error:
            logger.error(f"Error getting minimum gas prices: {error}")
            return "0.000025000000000000loya"
        __minimum_gas_prices = __minimum_gas_prices["minimum_gas_prices"][0]["amount"] + "loya"
    return __minimum_gas_prices

def minimum_tip_amount():
    global __minimum_tip_amount
    if __minimum_tip_amount == "0loya":
        __minimum_tip_amount, error = get_oracle_module_params()
        if error or __minimum_tip_amount is None:
            logger.error(f"Error getting minimum tip amount: {error}")
            return "10000loya"
        __minimum_tip_amount = __minimum_tip_amount["params"]["minTipAmount"] + "loya"
        logger.debug(f"Minimum tip amount set to: {__minimum_tip_amount}")
    return __minimum_tip_amount