import click
from dotenv import load_dotenv
import os
import sys
from typing import Optional
from src.relayer import start_relayer, data_bridge_init, data_bridge_reset, update_user_oracle_data
from src.bridge_client import relay_withdraw
from src.evm_client import EVMClient
from src.tipper import start_tipper
from src.layer_scraper import scrape_layer
from src.report import generate_power_report

try:
    from web3 import Web3
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False

def validate_required_env_vars(required_vars: list[str]) -> bool:
    """Validate that required environment variables are set and not empty"""
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.strip() == "":
            missing_vars.append(var)
    
    if missing_vars:
        click.echo(f"Error: Missing required environment variables: {', '.join(missing_vars)}", err=True)
        click.echo("Please set these variables in your .env file or as environment variables.", err=True)
        return False
    return True

def safe_int_from_env(var_name: str, default: int) -> int:
    """Safely convert environment variable to integer, handling comments"""
    value = os.getenv(var_name, str(default))
    if isinstance(value, str):
        # Remove inline comments
        value = value.split('#')[0].strip()
    try:
        return int(value)
    except (ValueError, TypeError):
        click.echo(f"Warning: Invalid value for {var_name}: '{os.getenv(var_name)}'. Using default: {default}", err=True)
        return default

def safe_str_from_env(var_name: str, default: str = "") -> str:
    """Safely get string from environment variable, handling comments"""
    value = os.getenv(var_name, default)
    if isinstance(value, str):
        # Remove inline comments and quotes
        value = value.split('#')[0].strip().strip('"\'')
    return value

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
def cli():
    """Layer Relayer CLI"""
    # Load .env file, overriding existing env vars
    load_dotenv(override=True)
    
    # Validate critical security settings
    eth_private_key = safe_str_from_env('ETH_PRIVATE_KEY')
    if eth_private_key and not eth_private_key.startswith('0x'):
        click.echo("Warning: ETH_PRIVATE_KEY should start with '0x'", err=True)

@cli.command()
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to relay')
@click.option('--sleep-time', type=int, help='Sleep time between relays in seconds')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', help='Layer RPC endpoint')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser', 'YoloTellorUser']), 
              default='SimpleLayerUser', help='Type of contract to use for relaying')
@click.option('--just-print', is_flag=True, help='Just print the oracle data parameters without submitting transaction')
def relay(query_id, sleep_time, eth_private_key, web3_provider, layer_swagger, layer_rpc, 
          data_bridge_address, layer_user_address, contract_type, just_print):
    """Start the relayer process"""
    
    # Handle sleep_time with safe parsing
    if sleep_time is None:
        sleep_time = safe_int_from_env('SLEEP_TIME', 600)
    
    # Get and clean environment variables
    query_id = query_id or safe_str_from_env('QUERY_ID')
    eth_private_key = eth_private_key or safe_str_from_env('ETH_PRIVATE_KEY')
    web3_provider = web3_provider or safe_str_from_env('WEB3_PROVIDER_URL')
    layer_swagger = layer_swagger or safe_str_from_env('LAYER_SWAGGER_ENDPOINT')
    layer_rpc = layer_rpc or safe_str_from_env('LAYER_RPC_ENDPOINT')
    data_bridge_address = to_checksum_address(data_bridge_address or safe_str_from_env('DATA_BRIDGE_CONTRACT_ADDRESS'))
    layer_user_address = to_checksum_address(layer_user_address or safe_str_from_env('LAYER_USER_CONTRACT_ADDRESS'))
    
    # Validate required variables
    required_vars = ['QUERY_ID', 'ETH_PRIVATE_KEY', 'WEB3_PROVIDER_URL', 'LAYER_SWAGGER_ENDPOINT', 
                    'LAYER_RPC_ENDPOINT', 'DATA_BRIDGE_CONTRACT_ADDRESS', 'LAYER_USER_CONTRACT_ADDRESS']
    
    # Set environment variables with cleaned values
    os.environ['QUERY_ID'] = query_id
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    os.environ['LAYER_USER_CONTRACT_ADDRESS'] = layer_user_address
    os.environ['SLEEP_TIME'] = str(sleep_time)
    os.environ['CONTRACT_TYPE'] = contract_type
    os.environ['JUST_PRINT'] = str(just_print)
    
    # Validate that all required environment variables are set
    if not validate_required_env_vars(required_vars):
        sys.exit(1)
    
    # Additional validation
    if not query_id.startswith('0x') or len(query_id) != 66:
        click.echo(f"Error: Invalid QUERY_ID format. Expected 64-character hex string starting with '0x'", err=True)
        sys.exit(1)
    
    if not eth_private_key.startswith('0x') or len(eth_private_key) != 66:
        click.echo(f"Error: Invalid ETH_PRIVATE_KEY format. Expected 64-character hex string starting with '0x'", err=True)
        sys.exit(1)
    
    if not data_bridge_address or not data_bridge_address.startswith('0x') or len(data_bridge_address) != 42:
        click.echo(f"Error: Invalid DATA_BRIDGE_CONTRACT_ADDRESS format. Expected 40-character hex string starting with '0x'", err=True)
        sys.exit(1)
    
    if not layer_user_address or not layer_user_address.startswith('0x') or len(layer_user_address) != 42:
        click.echo(f"Error: Invalid LAYER_USER_CONTRACT_ADDRESS format. Expected 40-character hex string starting with '0x'", err=True)
        sys.exit(1)
    
    try:
        start_relayer()
    except KeyboardInterrupt:
        click.echo("\nRelayer stopped by user.", err=True)
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error starting relayer: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
def init(eth_private_key, data_bridge_address, web3_provider, layer_swagger):
    """Initialize Tellor data bridge contract"""
    # Get and clean environment variables
    eth_private_key = eth_private_key or safe_str_from_env('ETH_PRIVATE_KEY')
    data_bridge_address = data_bridge_address or safe_str_from_env('DATA_BRIDGE_CONTRACT_ADDRESS')
    web3_provider = web3_provider or safe_str_from_env('WEB3_PROVIDER_URL')
    layer_swagger = layer_swagger or safe_str_from_env('LAYER_SWAGGER_ENDPOINT')
    
    # Validate required variables
    required_vars = ['ETH_PRIVATE_KEY', 'DATA_BRIDGE_CONTRACT_ADDRESS', 'WEB3_PROVIDER_URL', 'LAYER_SWAGGER_ENDPOINT']
    
    # Set cleaned values
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    if not validate_required_env_vars(required_vars):
        sys.exit(1)
    
    try:
        evm = EVMClient()
        evm.init_web3()
        evm.setup_data_bridge_contract()
        error = data_bridge_init(evm)
        if error:
            click.echo(f"Error initializing TellorDataBridge: {error}", err=True)
            sys.exit(1)
        click.echo("TellorDataBridge initialized successfully")
    except Exception as e:
        click.echo(f"Error initializing TellorDataBridge: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
def reset(eth_private_key, data_bridge_address, web3_provider, layer_swagger):
    """Reset Tellor data bridge contract"""
    # Get and clean environment variables
    eth_private_key = eth_private_key or safe_str_from_env('ETH_PRIVATE_KEY')
    data_bridge_address = data_bridge_address or safe_str_from_env('DATA_BRIDGE_CONTRACT_ADDRESS')
    web3_provider = web3_provider or safe_str_from_env('WEB3_PROVIDER_URL')
    layer_swagger = layer_swagger or safe_str_from_env('LAYER_SWAGGER_ENDPOINT')
    
    # Validate required variables
    required_vars = ['ETH_PRIVATE_KEY', 'DATA_BRIDGE_CONTRACT_ADDRESS', 'WEB3_PROVIDER_URL', 'LAYER_SWAGGER_ENDPOINT']
    
    # Set cleaned values
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    if not validate_required_env_vars(required_vars):
        sys.exit(1)
    
    try:
        evm = EVMClient()
        evm.init_web3()
        evm.setup_data_bridge_contract()
        error = data_bridge_reset(evm)
        if error:
            click.echo(f"Error resetting Tellor data bridge: {error}", err=True)
            sys.exit(1)
        click.echo("TellorDataBridge reset successfully")
    except Exception as e:
        click.echo(f"Error resetting Tellor data bridge: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to update')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser']), 
              default='SimpleLayerUser', help='Type of contract to use')
def update(query_id, contract_type):
    """Update oracle data for a specific query ID"""
    query_id = query_id or safe_str_from_env('QUERY_ID')
    
    if not query_id:
        click.echo("Error: QUERY_ID is required", err=True)
        sys.exit(1)
    
    try:
        tx_hash, error = update_user_oracle_data(query_id, contract_type)
        if error:
            click.echo(f"Error updating oracle data: {error}", err=True)
            sys.exit(1)
        click.echo(f"Oracle data updated. Transaction hash: {tx_hash.hex()}")
    except Exception as e:
        click.echo(f"Error updating oracle data: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--withdraw-id', type=int, help='Withdraw ID to relay')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--token-bridge-address', envvar='TOKEN_BRIDGE_CONTRACT_ADDRESS', help='Token Bridge contract address')
def relay_bridge(withdraw_id, eth_private_key, web3_provider, layer_swagger, data_bridge_address, token_bridge_address):
    """Relay a specific withdraw from Layer to EVM chain"""
    
    # Get withdraw_id from environment if not provided
    if withdraw_id is None:
        withdraw_id = safe_int_from_env('WITHDRAW_ID', 0)
    
    if withdraw_id <= 0:
        click.echo("Error: Valid withdraw ID is required", err=True)
        sys.exit(1)
    
    # Get and clean environment variables
    eth_private_key = eth_private_key or safe_str_from_env('ETH_PRIVATE_KEY')
    web3_provider = web3_provider or safe_str_from_env('WEB3_PROVIDER_URL')
    layer_swagger = layer_swagger or safe_str_from_env('LAYER_SWAGGER_ENDPOINT')
    data_bridge_address = data_bridge_address or safe_str_from_env('DATA_BRIDGE_CONTRACT_ADDRESS')
    token_bridge_address = token_bridge_address or safe_str_from_env('TOKEN_BRIDGE_CONTRACT_ADDRESS')
    
    # Set environment variables
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    os.environ['TOKEN_BRIDGE_CONTRACT_ADDRESS'] = token_bridge_address
    
    required_vars = ['ETH_PRIVATE_KEY', 'WEB3_PROVIDER_URL', 'LAYER_SWAGGER_ENDPOINT', 
                    'DATA_BRIDGE_CONTRACT_ADDRESS', 'TOKEN_BRIDGE_CONTRACT_ADDRESS']
    
    if not validate_required_env_vars(required_vars):
        sys.exit(1)
    
    try:
        status, error = relay_withdraw(withdraw_id)
        if error:
            click.echo(f"Error relaying withdraw: {error}", err=True)
            sys.exit(1)
        if status == 1:
            click.echo("Withdraw already claimed")
        elif status == 2:
            click.echo("Withdraw successfully relayed")
        else:
            click.echo("Withdraw not ready to be relayed")
    except Exception as e:
        click.echo(f"Error relaying withdraw: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to tip')
@click.option('--query-data', envvar='QUERY_DATA', help='Query data to tip')
@click.option('--layer-address', envvar='LAYER_ADDRESS', help='Layer address')
@click.option('--sleep-time', type=int, help='Sleep time between iterations in seconds')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', help='Layer RPC endpoint')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_CONTRACT_ADDRESS', help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser']), default='SimpleLayerUser', 
              help='Type of contract to use for relaying')
def tip(query_id, query_data, layer_address, layer_rpc, eth_private_key, web3_provider, layer_swagger, 
        data_bridge_address, layer_user_address, contract_type, sleep_time):
    """Start the tipper process"""
    
    # Handle sleep_time with safe parsing
    if sleep_time is None:
        sleep_time = safe_int_from_env('SLEEP_TIME', 3600)
    
    # Get and clean environment variables
    query_id = query_id or safe_str_from_env('QUERY_ID')
    query_data = query_data or safe_str_from_env('QUERY_DATA')
    layer_address = layer_address or safe_str_from_env('LAYER_ADDRESS')
    layer_rpc = layer_rpc or safe_str_from_env('LAYER_RPC_ENDPOINT')
    eth_private_key = eth_private_key or safe_str_from_env('ETH_PRIVATE_KEY')
    web3_provider = web3_provider or safe_str_from_env('WEB3_PROVIDER_URL')
    layer_swagger = layer_swagger or safe_str_from_env('LAYER_SWAGGER_ENDPOINT')
    data_bridge_address = data_bridge_address or safe_str_from_env('DATA_BRIDGE_CONTRACT_ADDRESS')
    layer_user_address = layer_user_address or safe_str_from_env('LAYER_USER_CONTRACT_ADDRESS')
    
    # Set environment variables
    os.environ['QUERY_ID'] = query_id
    os.environ['QUERY_DATA'] = query_data
    os.environ['LAYER_ADDRESS'] = layer_address
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['DATA_BRIDGE_CONTRACT_ADDRESS'] = data_bridge_address
    os.environ['LAYER_USER_CONTRACT_ADDRESS'] = layer_user_address
    os.environ['CONTRACT_TYPE'] = contract_type
    os.environ['SLEEP_TIME'] = str(sleep_time)
    
    required_vars = ['QUERY_ID', 'QUERY_DATA', 'LAYER_ADDRESS', 'LAYER_RPC_ENDPOINT']
    
    if not validate_required_env_vars(required_vars):
        sys.exit(1)
    
    try:
        start_tipper()
    except KeyboardInterrupt:
        click.echo("\nTipper stopped by user.", err=True)
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error starting tipper: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to scrape')
@click.option('--scrape-count', type=int, default=1000, help='Number of data points to scrape')
@click.option('--output-file', envvar='LAYER_DATA_CSV', default="data/layer_data.csv", help='Output CSV file path')
@click.option('--scrape-micro', is_flag=True, help='Scrape micro reports after aggregate data')
def scrape(query_id, scrape_count, output_file, scrape_micro):
    """Scrape historical data from Layer chain"""
    # Set environment variables
    os.environ['QUERY_ID'] = query_id
    os.environ['SCRAPE_COUNT'] = str(scrape_count)
    os.environ['LAYER_DATA_CSV'] = output_file

    print("scrape: Scraping layer data to ", output_file)

    scrape_layer(query_id, output_file, scrape_count, scrape_micro)

@cli.command()
@click.option('--input-file', envvar='LAYER_DATA_CSV', default="data/layer_data.csv", help='Input CSV file path')
@click.option('--terminal-plot', is_flag=True, help='Show plot in terminal')
@click.option('--micro', is_flag=True, help='Analyze micro reports')
def report(input_file, terminal_plot, micro):
    """Generate reports from scraped data"""
    if not os.path.exists(input_file):
        click.echo(f"Error: Input file {input_file} does not exist")
        return
    
    print(f"Generating reports from {input_file}")
    generate_power_report(input_file, show_terminal_plot=terminal_plot, micro_report=micro)
    print("\nReport generated in reports/power_vs_height.png")

if __name__ == '__main__':
    cli() 