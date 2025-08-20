from src.layer_client import strip_0x
from src.logger_utils import get_logger
import subprocess

logger = get_logger(__name__)

def tip(query_data, layer_address, layer_rpc_endpoint, chain_id="layertest-4", amount_loya=10000) -> Exception:
    # ensure all parameters are strings for subprocess
    # remove 0x prefix if it exists
    query_data_stripped = strip_0x(str(query_data))
    layer_address_str = str(layer_address)
    layer_rpc_endpoint_str = str(layer_rpc_endpoint)
    chain_id_str = str(chain_id)
    amount_loya_str = str(int(amount_loya)) + "loya"

    logger.debug(f"Tipping {amount_loya_str} for query {query_data_stripped}")
    logger.debug(f"Layer address: {layer_address_str}  Chain ID: {chain_id_str} Layer RPC Endpoint: {layer_rpc_endpoint_str}")
    try:
        result = subprocess.run(
            ["layerd", "tx", "oracle", "tip",
             query_data_stripped,
             amount_loya_str, 
             "--from", layer_address_str, 
             "--chain-id", chain_id_str, 
             "--fees", "5loya", 
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
        
        result = subprocess.run(
            ["layerd", "tx", "bridge", "request-attestations",
             layer_address_str,
             query_id_str,
             timestamp_str,
             "--from", layer_address_str,
             "--chain-id", chain_id_str,
             "--fees", "5loya",
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
