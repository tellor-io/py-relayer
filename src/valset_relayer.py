from src.relayer import handle_validator_set_update, sleep, fixed_interval_sleep
from src.logger_utils import get_logger
from src.evm_client import EVMClient
from src.layer_client import get_layer_chain_status
import os

logger = get_logger(__name__)

def start_valset_relayer():
    """Start the valset relayer process"""
    sleep_time = int(os.getenv("SLEEP_TIME", "600"))
    use_fixed_interval = os.getenv("FIXED_INTERVAL", "False").lower() == "true"
    
    logger.info(f"Starting valset relayer...")
    logger.info(f"Sleep time: {sleep_time} seconds")
    logger.info(f"Fixed interval mode: {use_fixed_interval}")

    evm = EVMClient()
    evm.init_web3()
    evm.setup_data_bridge_contract()
    
    while True:
        try:
            # Check layer chain status
            chain_status, _ = get_layer_chain_status()
            if chain_status:
                logger.warning(f"Layer chain status: {chain_status}")
                if use_fixed_interval:
                    fixed_interval_sleep(sleep_time)
                else:
                    sleep(sleep_time)
                continue

            # Valset update
            e = handle_validator_set_update(evm)
            if e:
                logger.error(f"Error handling validator set update: {e}")
            else:
                logger.info("Validator set up to date")
    
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
        # Sleep until next relay
        if use_fixed_interval:
            logger.debug(f"Using fixed interval sleep ({sleep_time}s)")
            fixed_interval_sleep(sleep_time)
        else:
            logger.debug(f"Using regular sleep ({sleep_time}s)")
            sleep(sleep_time)