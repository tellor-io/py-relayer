import click
from dotenv import load_dotenv
import os
from src.relayer import start_relayer, blobstream_init, blobstream_reset, update_user_oracle_data
from src.bridge_client import relay_withdraw
from src.evm_client import EVMClient
from src.tipper import start_tipper
from src.layer_scraper import scrape_layer
from src.report import generate_power_report

@click.group()
def cli():
    """Layer Relayer CLI"""
    # Load .env file as fallback
    load_dotenv()

@cli.command()
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to relay')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=600, help='Sleep time between relays in seconds')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--blobstream-address', envvar='BLOBSTREAM_CONTRACT_ADDRESS', help='Blobstream contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', help='Layer RPC endpoint')
def relay(query_id, sleep_time, eth_private_key, web3_provider, layer_swagger, layer_rpc, blobstream_address, layer_user_address):
    """Start the relayer process"""
    if eth_private_key:
        os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    if layer_swagger:
        os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    if layer_rpc:
        os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    if blobstream_address:
        os.environ['BLOBSTREAM_CONTRACT_ADDRESS'] = blobstream_address
    if layer_user_address:
        os.environ['LAYER_USER_CONTRACT_ADDRESS'] = layer_user_address
    if query_id:
        os.environ['QUERY_ID'] = query_id
    if sleep_time:
        os.environ['SLEEP_TIME'] = str(sleep_time)

    start_relayer()

@cli.command()
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--blobstream-address', envvar='BLOBSTREAM_CONTRACT_ADDRESS', required=True, help='Blobstream contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
def init(eth_private_key, blobstream_address, web3_provider, layer_swagger):
    """Initialize Blobstream contract"""
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['BLOBSTREAM_CONTRACT_ADDRESS'] = blobstream_address
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    evm = EVMClient()
    evm.init_web3()
    evm.setup_blobstream_contract()
    error = blobstream_init(evm)
    if error:
        click.echo(f"Error initializing Blobstream: {error}", err=True)
        exit(1)

@cli.command()
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--blobstream-address', envvar='BLOBSTREAM_CONTRACT_ADDRESS', required=True, help='Blobstream contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
def reset(eth_private_key, blobstream_address, web3_provider, layer_swagger):
    """Reset Blobstream contract"""
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['BLOBSTREAM_CONTRACT_ADDRESS'] = blobstream_address
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    evm = EVMClient()
    evm.init_web3()
    evm.setup_blobstream_contract()
    error = blobstream_reset(evm)
    if error:
        click.echo(f"Error resetting Blobstream: {error}", err=True)
        exit(1)

@cli.command()
@click.option('--query-id', required=True, help='Query ID to update')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--blobstream-address', envvar='BLOBSTREAM_CONTRACT_ADDRESS', required=True, help='Blobstream contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_CONTRACT_ADDRESS', required=True, help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', required=True, help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
def update(query_id, eth_private_key, blobstream_address, layer_user_address, web3_provider, layer_swagger):
    """Update oracle data for a specific query ID"""
    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['BLOBSTREAM_CONTRACT_ADDRESS'] = blobstream_address
    os.environ['LAYER_USER_CONTRACT_ADDRESS'] = layer_user_address
    os.environ['WEB3_PROVIDER_URL'] = web3_provider
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    
    evm = EVMClient()
    evm.init_web3()
    evm.setup_blobstream_contract()
    evm.setup_layer_user_contract()
    error = update_user_oracle_data(evm, query_id)
    if error:
        click.echo(f"Error updating oracle data: {error}", err=True)
        exit(1)

@cli.command()
@click.option('--withdraw-id', required=True, type=int, help='Withdraw ID to relay')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', help='Ethereum private key')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', help='Layer swagger endpoint')
@click.option('--blobstream-address', envvar='BLOBSTREAM_CONTRACT_ADDRESS', help='Blobstream contract address')
@click.option('--token-bridge-address', envvar='TOKEN_BRIDGE_CONTRACT_ADDRESS', help='Token Bridge contract address')
def relay_bridge(withdraw_id, eth_private_key, web3_provider, layer_swagger, blobstream_address, token_bridge_address):
    """Relay a specific withdraw from Layer to EVM chain"""
    if eth_private_key:
        os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    if layer_swagger:
        os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    if blobstream_address:
        os.environ['BLOBSTREAM_CONTRACT_ADDRESS'] = blobstream_address
    if token_bridge_address:
        os.environ['TOKEN_BRIDGE_CONTRACT_ADDRESS'] = token_bridge_address

    status, error = relay_withdraw(withdraw_id)
    if error:
        click.echo(f"Error relaying withdraw: {error}", err=True)
        exit(1)
    if status == 1:
        click.echo("Withdraw already claimed")
    elif status == 2:
        click.echo("Withdraw successfully relayed")
    else:
        click.echo("Withdraw not ready to be relayed")

@cli.command()
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to tip')
@click.option('--query-data', envvar='QUERY_DATA', required=True, help='Query data to tip')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=120, help='Sleep time between tips in seconds')
@click.option('--layer-address', envvar='LAYER_ADDRESS', required=True, help='Layer address')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
@click.option('--iterations', type=int, default=50, help='Number of iterations to run')
def tip(query_id, query_data, sleep_time, layer_address, layer_rpc, iterations):
    """Start the tipper process"""
    # Set environment variables
    os.environ['QUERY_ID'] = query_id
    os.environ['QUERY_DATA'] = query_data
    os.environ['SLEEP_TIME'] = str(sleep_time)
    os.environ['LAYER_ADDRESS'] = layer_address
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['N_ITERATIONS'] = str(iterations)

    start_tipper()

@cli.command()
@click.option('--query-id', envvar='QUERY_ID', required=True, help='Query ID to scrape')
@click.option('--scrape-count', type=int, default=1000, help='Number of data points to scrape')
@click.option('--output-file', envvar='LAYER_DATA_CSV', default="data/layer_data.csv", help='Output CSV file path')
def scrape(query_id, scrape_count, output_file):
    """Scrape historical data from Layer chain"""
    # Set environment variables
    os.environ['QUERY_ID'] = query_id
    os.environ['SCRAPE_COUNT'] = str(scrape_count)
    os.environ['LAYER_DATA_CSV'] = output_file

    print("scrape: Scraping layer data to ", output_file)

    scrape_layer(query_id, output_file, scrape_count)

@cli.command()
@click.option('--input-file', envvar='LAYER_DATA_CSV', default="data/layer_data.csv", help='Input CSV file path')
@click.option('--terminal-plot', is_flag=True, help='Show plot in terminal')
def report(input_file, terminal_plot):
    """Generate reports from scraped data"""
    if not os.path.exists(input_file):
        click.echo(f"Error: Input file {input_file} does not exist")
        return
    
    print(f"Generating reports from {input_file}")
    stats = generate_power_report(input_file, show_terminal_plot=terminal_plot)
    print("\nReport generated in reports/power_vs_height.png")

if __name__ == '__main__':
    cli() 