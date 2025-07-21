import click
from dotenv import load_dotenv
import os
from src.relayer import start_relayer, data_bridge_init, data_bridge_reset, update_user_oracle_data
from src.bridge_client import relay_withdraw
from src.evm_client import EVMClient
from src.tipper import start_tipper
from src.layer_scraper import scrape_layer
from src.report import generate_power_report
from src.logger_utils import setup_logging
from src.logger_utils import get_logger

logger = get_logger(__name__)

try:
    from web3 import Web3
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False

def add_logging_options(func):
    """Decorator to add logging options to commands"""
    func = click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')(func)
    func = click.option('--no-color', is_flag=True, help='Disable colored output')(func)
    return func

def configure_logging(verbose, no_color):
    """Configure logging based on options"""
    setup_logging(verbose=verbose, no_color=no_color)

def to_checksum_address(address: str) -> str:
    """Convert address to EIP-55 checksum format"""
    if not address or not address.startswith('0x'):
        return address
    
    if HAS_WEB3:
        try:
            return Web3.to_checksum_address(address)
        except Exception:
            # Fallback to lowercase if checksum fails
            return address.lower()
    else:
        # Fallback to lowercase if Web3 not available
        return address.lower()

@click.group()
@add_logging_options
@click.pass_context
def cli(ctx, verbose, no_color):
    """Layer Relayer CLI"""
    # Load .env file as fallback
    load_dotenv(override=True)
    
    # setup logging with global options - only once here
    configure_logging(verbose=verbose, no_color=no_color)
    
    # store options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['no_color'] = no_color

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to relay')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=600, help='Sleep time between relays in seconds')
@click.option('--fixed-interval', is_flag=True, help='Use fixed interval timing instead of fixed sleep duration')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', required=True, help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser', 'YoloTellorUser']), 
              default='SimpleLayerUser', help='Type of contract to use for relaying')
@click.option('--layer-tx-creator-address', envvar='LAYER_ADDRESS', required=True, help='Local keyring address used for creating transactions on layer')
@click.option('--just-print', is_flag=True, help='Just print the oracle data parameters without submitting transaction')
def relay(query_id, sleep_time, fixed_interval, eth_private_key, web3_provider, layer_swagger, layer_rpc, 
          data_bridge_address, layer_user_address, contract_type, just_print, layer_tx_creator_address, verbose, no_color):
    """Start the relayer process"""
    configure_logging(verbose=verbose, no_color=no_color)
    # Set environment variables
    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = to_checksum_address(data_bridge_address)
    os.environ['LAYER_USER_CONTRACT_ADDRESS'] = to_checksum_address(layer_user_address)
    os.environ['QUERY_ID'] = query_id
    os.environ['SLEEP_TIME'] = str(sleep_time)
    
    os.environ['CONTRACT_TYPE'] = contract_type
    os.environ['JUST_PRINT'] = str(just_print)
    os.environ['FIXED_INTERVAL'] = str(fixed_interval)
    os.environ['LAYER_ADDRESS'] = to_checksum_address(layer_tx_creator_address)
    try:
        start_relayer()
    except KeyboardInterrupt:
        logger.info("\nRelayer stopped by user.")
        exit(0)
    except Exception as e:
        logger.error(f"Error starting relayer: {e}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
def init(eth_private_key, data_bridge_address, web3_provider, layer_swagger, verbose, no_color):
    """Initialize Tellor data bridge contract"""
    configure_logging(verbose=verbose, no_color=no_color)

    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    try:
        evm = EVMClient()
        evm.init_web3()
        evm.setup_data_bridge_contract()
        error = data_bridge_init(evm)
        if error:
            logger.error(f"Error initializing TellorDataBridge: {error}")
            exit(1)
    except Exception as e:
        logger.error(f"Error initializing TellorDataBridge: {e}")
        exit(1)

@cli.command()
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
def reset(eth_private_key, data_bridge_address, web3_provider, layer_swagger, verbose, no_color):
    """Reset Tellor data bridge contract"""
    configure_logging(verbose=verbose, no_color=no_color)

    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = to_checksum_address(data_bridge_address)
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    try:
        evm = EVMClient()
        evm.init_web3()
        evm.setup_data_bridge_contract()
        error = data_bridge_reset(evm)
        if error:
            logger.error(f"Error resetting Tellor data bridge: {error}")
            exit(1)
    except Exception as e:
        logger.error(f"Error resetting Tellor data bridge: {e}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to update')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser']), 
              default='SimpleLayerUser', help='Type of contract to use')
def update(query_id, contract_type, verbose, no_color):
    """Update oracle data for a specific query ID"""
    configure_logging(verbose=verbose, no_color=no_color)

    try:
        tx_hash, error = update_user_oracle_data(query_id, contract_type)
        if error:
            logger.error(f"Error updating oracle data: {error}")
            exit(1)
        logger.info(f"Oracle data updated. Transaction hash: {tx_hash.hex()}")
    except Exception as e:
        logger.error(f"Error updating oracle data: {e}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--withdraw-id', required=True, type=int, help='Withdraw ID to relay')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--token-bridge-address', envvar='TOKEN_BRIDGE_CONTRACT_ADDRESS', required=True, help='Token Bridge contract address')
@click.option('--layer-tx-creator-address', envvar='LAYER_ADDRESS', required=True, help='Local keyring address used for creating transactions on layer')
def relay_bridge(withdraw_id, eth_private_key, web3_provider, layer_swagger, data_bridge_address, token_bridge_address, layer_tx_creator_address, verbose, no_color):
    """Relay a specific withdraw from Layer to EVM chain"""
    configure_logging(verbose=verbose, no_color=no_color)
    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = to_checksum_address(data_bridge_address)
    os.environ['TOKEN_BRIDGE_CONTRACT_ADDRESS'] = to_checksum_address(token_bridge_address)
    os.environ['LAYER_ADDRESS'] = layer_tx_creator_address

    _, error = relay_withdraw(withdraw_id)
    if error:
        logger.error(f"Error relaying withdraw: {error}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to tip')
@click.option('--query-data', envvar='QUERY_DATA', required=True, help='Query data to tip')
@click.option('--layer-address', envvar='LAYER_ADDRESS', required=True, help='Layer address')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=3600, help='Sleep time between iterations in seconds')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
@click.option('--contract-type', envvar='CONTRACT_TYPE', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser']), default='SimpleLayerUser', 
              help='Type of contract to use for relaying')
def tip(query_id, query_data, layer_address, layer_rpc, eth_private_key, web3_provider, layer_swagger, 
        data_bridge_address, layer_user_address, contract_type, sleep_time, verbose, no_color):
    """Start the tipper process"""
    configure_logging(verbose=verbose, no_color=no_color)
    # Set environment variables
    os.environ['QUERY_ID'] = query_id
    os.environ['QUERY_DATA'] = query_data
    os.environ['LAYER_ADDRESS'] = layer_address
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = to_checksum_address(data_bridge_address)
    os.environ['LAYER_USER_CONTRACT_ADDRESS'] = to_checksum_address(layer_user_address)
    os.environ['CONTRACT_TYPE'] = contract_type
    os.environ['SLEEP_TIME'] = str(sleep_time)
    
    try:
        start_tipper()
    except KeyboardInterrupt:
        logger.info("\nTipper stopped by user.")
        exit(0)
    except Exception as e:
        logger.error(f"Error starting tipper: {e}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to scrape')
@click.option('--scrape-count', type=int, default=1000, help='Number of data points to scrape')
@click.option('--output-file', envvar='LAYER_DATA_CSV', default="data/layer_data.csv", help='Output CSV file path')
@click.option('--scrape-micro', is_flag=True, help='Scrape micro reports after aggregate data')
def scrape(query_id, scrape_count, output_file, scrape_micro, verbose, no_color):
    """Scrape historical data from Layer chain"""
    configure_logging(verbose=verbose, no_color=no_color)
    # Set environment variables
    os.environ['QUERY_ID'] = query_id
    os.environ['SCRAPE_COUNT'] = str(scrape_count)
    os.environ['LAYER_DATA_CSV'] = output_file

    logger.info(f"Scraping layer data to {output_file}")

    scrape_layer(query_id, output_file, scrape_count, scrape_micro)

@cli.command()
@add_logging_options
@click.option('--input-file', envvar='LAYER_DATA_CSV', default="data/layer_data.csv", help='Input CSV file path')
@click.option('--terminal-plot', is_flag=True, help='Show plot in terminal')
@click.option('--micro', is_flag=True, help='Analyze micro reports')
def report(input_file, terminal_plot, micro, verbose, no_color):
    """Generate reports from scraped data"""
    configure_logging(verbose=verbose, no_color=no_color)
    if not os.path.exists(input_file):
        logger.error(f"Input file {input_file} does not exist")
        return
    
    logger.info(f"Generating reports from {input_file}")
    stats = generate_power_report(input_file, show_terminal_plot=terminal_plot, micro_report=micro)
    logger.info("\nReport generated in reports/power_vs_height.png")

if __name__ == '__main__':
    cli() 