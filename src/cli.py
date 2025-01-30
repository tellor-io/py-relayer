import click
from dotenv import load_dotenv
import os
from src.relayer import start_relayer, blobstream_init, blobstream_reset, update_user_oracle_data
from src.evm_client import init_web3

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
def relay(query_id, sleep_time, eth_private_key, blobstream_address, layer_user_address, 
         web3_provider, layer_swagger, layer_rpc):
    """Start the relayer process"""
    # Only set environment variables for values that were actually provided
    # (either via CLI or environment)
    if query_id:
        os.environ['QUERY_ID'] = query_id
    if sleep_time:
        os.environ['SLEEP_TIME'] = str(sleep_time)
    if eth_private_key:
        os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    if blobstream_address:
        os.environ['BLOBSTREAM_CONTRACT_ADDRESS'] = blobstream_address
    if layer_user_address:
        os.environ['LAYER_USER_CONTRACT_ADDRESS'] = layer_user_address
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    if layer_swagger:
        os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    if layer_rpc:
        os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    
    from src.relayer import start_relayer
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
    
    init_web3()
    error = blobstream_init()
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
    
    init_web3()
    error = blobstream_reset()
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
    
    init_web3()
    error = update_user_oracle_data(query_id)
    if error:
        click.echo(f"Error updating oracle data: {error}", err=True)
        exit(1)

if __name__ == '__main__':
    cli() 