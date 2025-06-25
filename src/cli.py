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

def add_logging_options(func):
    """Decorator to add logging options to commands"""
    func = click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')(func)
    func = click.option('--no-color', is_flag=True, help='Disable colored output')(func)
    return func

def configure_logging(verbose, no_color):
    """Configure logging based on options"""
    setup_logging(verbose=verbose, no_color=no_color)

@click.group()
@add_logging_options
@click.pass_context
def cli(ctx, verbose, no_color):
    """Layer Relayer CLI"""
    # Load .env file as fallback
    load_dotenv()
    
    # setup logging with global options - only once here
    configure_logging(verbose=verbose, no_color=no_color)
    
    # store options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['no_color'] = no_color

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to relay')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=600, help='Sleep time between relays in seconds')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', help='Layer RPC endpoint')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser', 'YoloTellorUser']), 
              default='SimpleLayerUser', help='Type of contract to use for relaying')
@click.option('--layer-tx-creator-address', envvar='LAYER_ADDRESS', help='Local keyring address used for creating transactions on layer')
@click.option('--just-print', is_flag=True, help='Just print the oracle data parameters without submitting transaction')
def relay(query_id, sleep_time, eth_private_key, web3_provider, layer_swagger, layer_rpc, 
          data_bridge_address, layer_user_address, contract_type, just_print, layer_tx_creator_address, verbose, no_color):
    """Start the relayer process"""
    configure_logging(verbose=verbose, no_color=no_color)
    # Set environment variables
    if eth_private_key:
        os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    if layer_swagger:
        os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    if layer_rpc:
        os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    if data_bridge_address:
        os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    if layer_user_address:
        os.environ['LAYER_USER_CONTRACT_ADDRESS'] = layer_user_address
    if query_id:
        os.environ['QUERY_ID'] = query_id
    if sleep_time:
        os.environ['SLEEP_TIME'] = str(sleep_time)
    
    os.environ['CONTRACT_TYPE'] = contract_type
    os.environ['JUST_PRINT'] = str(just_print)
    if layer_tx_creator_address:
        os.environ['LAYER_ADDRESS'] = layer_tx_creator_address
    start_relayer()

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
    
    evm = EVMClient()
    evm.init_web3()
    evm.setup_data_bridge_contract()
    error = data_bridge_init(evm)
    if error:
        logger.error(f"Error initializing TellorDataBridge: {error}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
def reset(eth_private_key, data_bridge_address, web3_provider, layer_swagger, verbose, no_color):
    """Reset Tellor data bridge contract"""
    configure_logging(verbose=verbose, no_color=no_color)
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    evm = EVMClient()
    evm.init_web3()
    evm.setup_data_bridge_contract()
    error = data_bridge_reset(evm)
    if error:
        logger.error(f"Error resetting Tellor data bridge: {error}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to update')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser']), 
              default='SimpleLayerUser', help='Type of contract to use')
def update(query_id, contract_type, verbose, no_color):
    """Update oracle data for a specific query ID"""
    configure_logging(verbose=verbose, no_color=no_color)
    tx_hash, error = update_user_oracle_data(query_id, contract_type)
    if error:
        logger.error(f"Error updating oracle data: {error}")
        exit(1)
    logger.info(f"Oracle data updated. Transaction hash: {tx_hash.hex()}")

@cli.command()
@add_logging_options
@click.option('--withdraw-id', required=True, type=int, help='Withdraw ID to relay')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--token-bridge-address', envvar='TOKEN_BRIDGE_CONTRACT_ADDRESS', help='Token Bridge contract address')
@click.option('--layer-tx-creator-address', envvar='LAYER_ADDRESS', help='Local keyring address used for creating transactions on layer')
def relay_bridge(withdraw_id, eth_private_key, web3_provider, layer_swagger, data_bridge_address, token_bridge_address, layer_tx_creator_address, verbose, no_color):
    """Relay a specific withdraw from Layer to EVM chain"""
    configure_logging(verbose=verbose, no_color=no_color)
    if eth_private_key:
        os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    if layer_swagger:
        os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    if data_bridge_address:
        os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    if token_bridge_address:
        os.environ['TOKEN_BRIDGE_CONTRACT_ADDRESS'] = token_bridge_address
    if layer_tx_creator_address:
        os.environ['LAYER_ADDRESS'] = layer_tx_creator_address

    _, error = relay_withdraw(withdraw_id)
    if error:
        logger.error(f"Error relaying withdraw: {error}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to tip')
@click.option('--query-data', envvar='QUERY_DATA', help='Query data to tip')
@click.option('--layer-address', envvar='LAYER_ADDRESS', help='Layer address')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=3600, help='Sleep time between iterations in seconds')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', help='Layer RPC endpoint')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--contract-type', envvar='CONTRACT_TYPE', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser']), default='SimpleLayerUser', 
              help='Type of contract to use for relaying')
def tip(query_id, query_data, layer_address, layer_rpc, eth_private_key, web3_provider, layer_swagger, 
        data_bridge_address, layer_user_address, contract_type, sleep_time, verbose, no_color):
    """Start the tipper process"""
    configure_logging(verbose=verbose, no_color=no_color)
    # Set environment variables
    if query_id:
        os.environ['QUERY_ID'] = query_id
    if query_data:
        os.environ['QUERY_DATA'] = query_data
    if layer_address:
        os.environ['LAYER_ADDRESS'] = layer_address
    if layer_rpc:
        os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    if eth_private_key:
        os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    if layer_swagger:
        os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    if data_bridge_address:
        os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    if layer_user_address:
        os.environ['LAYER_USER_CONTRACT_ADDRESS'] = layer_user_address
    if contract_type:
        os.environ['CONTRACT_TYPE'] = contract_type
    if sleep_time:
        os.environ['SLEEP_TIME'] = str(sleep_time)
    
    start_tipper()

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