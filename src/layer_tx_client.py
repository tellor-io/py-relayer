from src.layer_client import strip_0x, get_minimum_gas_prices, get_oracle_module_params
from src.logger_utils import get_logger
import subprocess

logger = get_logger(__name__)
__minimum_gas_prices = "0loya"
__minimum_tip_amount = "0loya"

def tip(query_data, layer_address, layer_rpc_endpoint, chain_id="layertest-4") -> Exception:
    # ensure all parameters are strings for subprocess
    # remove 0x prefix if it exists
    query_data_stripped = strip_0x(str(query_data))
    layer_address_str = str(layer_address)
    layer_rpc_endpoint_str = str(layer_rpc_endpoint)
    chain_id_str = str(chain_id)
    gas_price = minimum_gas_prices()
    min_tip_amount = minimum_tip_amount()

    logger.debug(f"Tipping {min_tip_amount} for query {query_data_stripped}")
    logger.debug(f"Layer address: {layer_address_str}  Chain ID: {chain_id_str} Layer RPC Endpoint: {layer_rpc_endpoint_str}")
    try:
        result = subprocess.run(
            ["layerd", "tx", "oracle", "tip",
             query_data_stripped,
             min_tip_amount, 
             "--from", layer_address_str, 
             "--chain-id", chain_id_str,
             "--gas=auto",
             "--gas-adjustment=1.5",
             "--gas-prices", gas_price,
             "--keyring-backend", "test", 
             "--yes", 
             "--node=" + layer_rpc_endpoint_str],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Tip result:")
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("Error executing tip command:")
        logger.error(f"Exit code: {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise

def request_attestations(query_id, timestamp, layer_address, layer_rpc_endpoint, chain_id="layertest-4") -> Exception:
    try:
        # ensure all parameters are strings for subprocess
        # remove 0x prefix if it exists
        query_id_str = strip_0x(str(query_id))
        timestamp_str = str(timestamp)
        layer_address_str = str(layer_address)
        layer_rpc_endpoint_str = str(layer_rpc_endpoint)
        chain_id_str = str(chain_id)
        gas_price = minimum_gas_prices()
        
        result = subprocess.run(
            ["layerd", "tx", "bridge", "request-attestations",
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
             "--node=" + layer_rpc_endpoint_str],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Request attestations result:")
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("Error executing request attestations command:")
        logger.error(f"Exit code: {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise

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