import click
from dotenv import load_dotenv
import os
from src.relayer import start_relayer, update_user_oracle_data, data_bridge_init, data_bridge_reset
from src.threshold_relayer import start_primary_threshold_relayer, start_backup_threshold_relayer
from src.bridge_client import relay_withdraw
from src.layer_tx_client import tip as layer_tip
from src.evm_client import EVMClient
from src.logger_utils import setup_logging
from src.logger_utils import get_logger
from src.valset_relayer import start_valset_relayer
from src.query_parser import QueryParser
from src.config_loader import load_config, apply_env, build_default_map
from src.price_service import run_price_service
from eth_utils import decode_hex

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

def parse_query_string_if_provided(query_string, query_id, query_data):
    """
    Parse query string if provided, otherwise use existing query_id and query_data
    
    Args:
        query_string: Optional query string like "SpotPrice(eth,usd)"
        query_id: Existing query_id (used if query_string not provided)
        query_data: Existing query_data (used if query_string not provided)
        
    Returns:
        Tuple of (final_query_id, final_query_data)
    """
    if query_string:
        logger.info(f"Parsing query string: {query_string}")
        parser = QueryParser()
        query_info = parser.get_query_info(query_string)
        logger.info(f"Generated queryId: {query_info['queryId']}")
        logger.info(f"Query type: {query_info['queryType']}")
        if query_info['hasDefinition']:
            logger.info("Using predefined query type definition")
        else:
            logger.info("Using inline type definitions")
        return query_info['queryId'], query_info['queryData']
    else:
        return query_id, query_data

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
@click.option('--config', '-c', help='Config name or path', default=None)
@click.pass_context
def cli(ctx, verbose, no_color, config):
    """Layer Relayer CLI"""
    # Load .env file as fallback
    load_dotenv(override=True)
    
    # setup logging with global options - only once here
    configure_logging(verbose=verbose, no_color=no_color)
    
    # Load config if provided, apply env and command defaults
    try:
        cfg = load_config(config)
        if cfg:
            apply_env(cfg)
            # Attach command defaults for subcommands
            ctx.default_map = (ctx.default_map or {})
            # Merge existing default_map with our config-based defaults
            cfg_defaults = build_default_map(cfg)
            # Shallow merge at top level (per command mapping)
            for k, v in cfg_defaults.items():
                prev = ctx.default_map.get(k, {}) if isinstance(ctx.default_map, dict) else {}
                if isinstance(prev, dict):
                    merged = dict(prev)
                    merged.update(v)
                    ctx.default_map[k] = merged
                else:
                    ctx.default_map[k] = v
    except Exception as e:
        logger.error(f"Failed to load config '{config}': {e}")
        exit(1)
    
    # store options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['no_color'] = no_color

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to relay (alternative to --query-string)')
@click.option('--query-string', envvar='QUERY_STRING', help='Query string like "SpotPrice(eth,usd)" (alternative to --query-id)')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=600, help='Sleep time between relays in seconds')
@click.option('--fixed-interval', is_flag=True, help='Use fixed interval timing instead of fixed sleep duration')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_ADDRESS', required=True, help='Layer user contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL (overrides --evm-network)')
@click.option('--evm-network', envvar='EVM_NETWORK', help='EVM network name from evm-networks config (used if --web3-provider not set)')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser', 'YoloTellorUser', 'TellorDataBank']), 
              default='SimpleLayerUser', help='Type of contract to use for relaying')
@click.option('--layer-tx-creator-address', envvar='LAYER_TX_CREATOR_ADDRESS', required=True, help='Local keyring address used for creating transactions on layer')
@click.option('--just-print', is_flag=True, help='Just print the oracle data parameters without submitting transaction')
def relay(query_id, query_string, sleep_time, fixed_interval, eth_private_key, web3_provider, evm_network, layer_swagger, layer_rpc, 
          data_bridge_address, layer_user_address, contract_type, just_print, layer_tx_creator_address, verbose, no_color):
    """Start the relayer process"""
    configure_logging(verbose=verbose, no_color=no_color)
    
    # validate that either query_id or query_string is provided
    if not query_id and not query_string:
        logger.error("Either --query-id or --query-string must be provided")
        exit(1)
    
    # parse query string if provided
    final_query_id, final_query_data = parse_query_string_if_provided(query_string, query_id, None)
    
    # Set environment variables
    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    elif evm_network:
        os.environ['EVM_NETWORK'] = evm_network
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['DATA_BRIDGE_ADDRESS'] = to_checksum_address(data_bridge_address)
    os.environ['LAYER_USER_ADDRESS'] = to_checksum_address(layer_user_address)
    os.environ['QUERY_ID'] = final_query_id
    if final_query_data:
        os.environ['QUERY_DATA'] = final_query_data
    os.environ['SLEEP_TIME'] = str(sleep_time)
    
    os.environ['CONTRACT_TYPE'] = contract_type
    os.environ['JUST_PRINT'] = str(just_print)
    os.environ['FIXED_INTERVAL'] = str(fixed_interval)
    os.environ['LAYER_TX_CREATOR_ADDRESS'] = to_checksum_address(layer_tx_creator_address)
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
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL (overrides --evm-network)')
@click.option('--evm-network', envvar='EVM_NETWORK', help='EVM network name from evm-networks config (used if --web3-provider not set)')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
def init(eth_private_key, data_bridge_address, web3_provider, evm_network, layer_swagger, verbose, no_color):
    """Initialize Tellor data bridge contract"""
    configure_logging(verbose=verbose, no_color=no_color)

    os.environ['ETH_PRIVATE_KEY'] = eth_private_key
    os.environ['DATA_BRIDGE_ADDRESS'] = data_bridge_address
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    elif evm_network:
        os.environ['EVM_NETWORK'] = evm_network
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
@add_logging_options
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL (overrides --evm-network)')
@click.option('--evm-network', envvar='EVM_NETWORK', help='EVM network name from evm-networks config (used if --web3-provider not set)')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
@click.option('--just-print', is_flag=True, help='Just print the reset parameters without submitting transaction')
def reset(eth_private_key, data_bridge_address, web3_provider, evm_network, layer_swagger, just_print, verbose, no_color):
    """Reset Tellor data bridge contract"""
    configure_logging(verbose=verbose, no_color=no_color)

    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    os.environ['DATA_BRIDGE_ADDRESS'] = to_checksum_address(data_bridge_address)
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    elif evm_network:
        os.environ['EVM_NETWORK'] = evm_network
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['JUST_PRINT'] = str(just_print)
    
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
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to update (alternative to --query-string)')
@click.option('--query-string', envvar='QUERY_STRING', help='Query string like "SpotPrice(eth,usd)" (alternative to --query-id)')
@click.option('--contract-type', type=click.Choice(['SimpleLayerUser', 'TestPriceFeedUser']), 
              default='SimpleLayerUser', help='Type of contract to use')
def update(query_id, query_string, contract_type, verbose, no_color):
    """Update oracle data for a specific query ID"""
    configure_logging(verbose=verbose, no_color=no_color)

    # validate that either query_id or query_string is provided
    if not query_id and not query_string:
        logger.error("Either --query-id or --query-string must be provided")
        exit(1)
    
    # parse query string if provided
    final_query_id, _ = parse_query_string_if_provided(query_string, query_id, None)

    try:
        tx_hash, error = update_user_oracle_data(final_query_id, contract_type)
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
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL (overrides --evm-network)')
@click.option('--evm-network', envvar='EVM_NETWORK', help='EVM network name from evm-networks config (used if --web3-provider not set)')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--token-bridge-address', envvar='TOKEN_BRIDGE_ADDRESS', help='Token Bridge V2 contract address (default when not using --legacy)')
@click.option('--token-bridge-legacy-address', envvar='TOKEN_BRIDGE_LEGACY_ADDRESS', help='Token Bridge V1 contract address (only used with --legacy)')
@click.option('--layer-tx-creator-address', envvar='LAYER_TX_CREATOR_ADDRESS', required=True, help='Local keyring address used for creating transactions on layer')
@click.option('--legacy', is_flag=True, help='Relay to legacy TokenBridge V1 (TRBBridge query type, uses TOKEN_BRIDGE_LEGACY_ADDRESS)')
@click.option('--reverify', is_flag=True, help='Call TokenBridgeV2.reverifyExtraWithdraw for an existing withdraw with pending amount')
def relay_bridge(withdraw_id, eth_private_key, web3_provider, evm_network, layer_swagger, layer_rpc, data_bridge_address, token_bridge_address, token_bridge_legacy_address, layer_tx_creator_address, legacy, reverify, verbose, no_color):
    """Relay a withdraw from Layer to EVM (default: V2 withdrawFromLayer). Use --legacy for V1 bridge, --reverify for reverifyExtraWithdraw."""
    configure_logging(verbose=verbose, no_color=no_color)
    if legacy and reverify:
        logger.error("Cannot use both --legacy and --reverify")
        exit(1)
    if legacy and not token_bridge_legacy_address:
        logger.error("TOKEN_BRIDGE_LEGACY_ADDRESS (or --token-bridge-legacy-address) is required when using --legacy")
        exit(1)
    if not legacy and not token_bridge_address:
        logger.error("TOKEN_BRIDGE_ADDRESS (or --token-bridge-address) is required for V2 relay (default or --reverify)")
        exit(1)
    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    elif evm_network:
        os.environ['EVM_NETWORK'] = evm_network
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['DATA_BRIDGE_ADDRESS'] = to_checksum_address(data_bridge_address)
    if token_bridge_address:
        os.environ['TOKEN_BRIDGE_ADDRESS'] = to_checksum_address(token_bridge_address)
    if token_bridge_legacy_address:
        os.environ['TOKEN_BRIDGE_LEGACY_ADDRESS'] = to_checksum_address(token_bridge_legacy_address)
    os.environ['LAYER_TX_CREATOR_ADDRESS'] = layer_tx_creator_address

    _, error = relay_withdraw(withdraw_id, legacy=legacy, reverify=reverify)
    if error:
        logger.error(f"Error relaying withdraw: {error}")
        exit(1)

@cli.command()
@add_logging_options
@click.argument('query_data')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
@click.option('--layer-tx-creator-address', envvar='LAYER_TX_CREATOR_ADDRESS', required=True, help='Local keyring address used for creating transactions on layer')
@click.option('--chain-id', envvar='CHAIN_ID', default=None, help='Layer chain ID (auto-detected from node when not set)')
def tip(query_data, layer_rpc, layer_tx_creator_address, chain_id, verbose, no_color):
    """Submit an oracle tip for a given query data."""
    configure_logging(verbose=verbose, no_color=no_color)
    error = layer_tip(query_data, layer_tx_creator_address, layer_rpc, chain_id)
    if error:
        logger.error(f"Error tipping: {error}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=600, help='Sleep time between relays in seconds')
@click.option('--fixed-interval', is_flag=True, help='Use fixed interval timing instead of fixed sleep duration')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL (overrides --evm-network)')
@click.option('--evm-network', envvar='EVM_NETWORK', help='EVM network name from evm-networks config (used if --web3-provider not set)')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
def relay_valset(sleep_time, fixed_interval, eth_private_key, web3_provider, evm_network, layer_swagger, layer_rpc, 
          data_bridge_address, verbose, no_color):
    """Start the valset relayer process"""
    configure_logging(verbose=verbose, no_color=no_color)
    # Set environment variables
    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    elif evm_network:
        os.environ['EVM_NETWORK'] = evm_network
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['DATA_BRIDGE_ADDRESS'] = to_checksum_address(data_bridge_address)
    os.environ['SLEEP_TIME'] = str(sleep_time)
    os.environ['FIXED_INTERVAL'] = str(fixed_interval)
    try:
        start_valset_relayer()
    except KeyboardInterrupt:
        logger.info("\nValset relayer stopped by user.")
        exit(0)
    except Exception as e:
        logger.error(f"Error starting valset relayer: {e}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--query-id', envvar='QUERY_ID', help='Query ID to relay (alternative to --query-string)')
@click.option('--query-data', envvar='QUERY_DATA', help='Query data to relay (alternative to --query-string)')
@click.option('--query-string', envvar='QUERY_STRING', help='Query string like "SpotPrice(eth,usd)" (alternative to --query-id/--query-data)')
@click.option('--sleep-time', envvar='SLEEP_TIME', type=int, default=600, help='Heartbeat interval in seconds')
@click.option('--price-threshold', envvar='PRICE_THRESHOLD', type=float, required=True, help='Price change threshold as decimal (e.g., 0.01 for 1%)')
@click.option('--check-interval', envvar='CHECK_INTERVAL', type=int, default=300, help='Main loop interval in seconds')
@click.option('--price-api-url', envvar='PRICE_API_URL', help='CoinGecko price API URL (optional, falls back to Layer chain)')
@click.option('--eth-private-key', envvar='ETH_PRIVATE_KEY', required=True, help='Ethereum private key. Should use .env file for this.')
@click.option('--data-bridge-address', envvar='DATA_BRIDGE_ADDRESS', required=True, help='Tellor data bridge contract address')
@click.option('--layer-user-address', envvar='LAYER_USER_ADDRESS', required=True, help='TellorDataBank contract address')
@click.option('--web3-provider', envvar='WEB3_PROVIDER_URL', help='Web3 provider URL (overrides --evm-network)')
@click.option('--evm-network', envvar='EVM_NETWORK', help='EVM network name from evm-networks config (used if --web3-provider not set)')
@click.option('--layer-swagger', envvar='LAYER_SWAGGER_ENDPOINT', required=True, help='Layer swagger API endpoint')
@click.option('--layer-rpc', envvar='LAYER_RPC_ENDPOINT', required=True, help='Layer RPC endpoint')
@click.option('--layer-tx-creator-address', envvar='LAYER_TX_CREATOR_ADDRESS', required=True, help='Local keyring address used for creating transactions on layer')
@click.option('--optimistic-delay', envvar='OPTIMISTIC_DELAY', type=int, default=43200, help='Optimistic delay in seconds')
@click.option('--max-attestation-age', envvar='MAX_ATTESTATION_AGE', type=int, default=600, help='Max attestation age in seconds')
@click.option('--max-data-age', envvar='MAX_DATA_AGE', type=int, default=86400, help='Max data age in seconds')
@click.option('--min-stake-percentage', envvar='MIN_STAKE_PERCENTAGE', type=int, default=33, help='Min stake percentage for optimistic data')
@click.option('--offset', envvar='OFFSET', type=int, default=0, help='Offset in seconds for the next heartbeat time')
@click.option('--backup', is_flag=True, help='Run the relayer in backup mode')
def relay_threshold(query_id, query_data, query_string, sleep_time, price_threshold, check_interval, price_api_url, eth_private_key, 
                    web3_provider, evm_network, layer_swagger, layer_rpc, data_bridge_address, layer_user_address, 
                    layer_tx_creator_address, optimistic_delay, max_attestation_age, max_data_age, 
                    min_stake_percentage, offset, backup, verbose, no_color):
    """Start the threshold relayer process (heartbeat + price threshold)"""
    configure_logging(verbose=verbose, no_color=no_color)
    logger.info(f"Starting threshold relayer")
    
    # validate that either query_id/query_data or query_string is provided
    if query_string:
        if query_id or query_data:
            logger.warning("Both --query-string and --query-id/--query-data provided. Using --query-string.")
        final_query_id, final_query_data = parse_query_string_if_provided(query_string, None, None)
    elif query_id and query_data:
        final_query_id, final_query_data = query_id, query_data
    else:
        logger.error("Either --query-string or both --query-id and --query-data must be provided")
        exit(1)
    
    # set environment variables
    os.environ['ETH_PRIVATE_KEY'] = to_checksum_address(eth_private_key)
    if web3_provider:
        os.environ['WEB3_PROVIDER_URL'] = web3_provider
    elif evm_network:
        os.environ['EVM_NETWORK'] = evm_network
    os.environ['LAYER_SWAGGER_ENDPOINT'] = layer_swagger
    os.environ['LAYER_RPC_ENDPOINT'] = layer_rpc
    os.environ['DATA_BRIDGE_ADDRESS'] = to_checksum_address(data_bridge_address)
    os.environ['LAYER_USER_ADDRESS'] = to_checksum_address(layer_user_address)
    os.environ['QUERY_ID'] = final_query_id
    os.environ['QUERY_DATA'] = final_query_data
    os.environ['SLEEP_TIME'] = str(sleep_time)
    os.environ['PRICE_THRESHOLD'] = str(price_threshold)
    os.environ['CHECK_INTERVAL'] = str(check_interval)
    os.environ['LAYER_TX_CREATOR_ADDRESS'] = to_checksum_address(layer_tx_creator_address)
    os.environ['OPTIMISTIC_DELAY'] = str(optimistic_delay)
    os.environ['MAX_ATTESTATION_AGE'] = str(max_attestation_age)
    os.environ['MAX_DATA_AGE'] = str(max_data_age)
    os.environ['MIN_STAKE_PERCENTAGE'] = str(min_stake_percentage)
    os.environ['OFFSET'] = str(offset)
    if price_api_url:
        os.environ['PRICE_API_URL'] = price_api_url
    
    try:
        if backup:
            start_backup_threshold_relayer()
        else:
            start_primary_threshold_relayer()
    except KeyboardInterrupt:
        logger.info("\nImproved threshold relayer stopped by user.")
        exit(0)
    except Exception as e:
        logger.error(f"Error starting improved threshold relayer: {e}")
        exit(1)

@cli.command()
@add_logging_options
@click.option('--query-string', '-q', required=True, help='Query string to parse and validate')
def parse_query(query_string, verbose, no_color):
    """
    Parse and validate a query string, showing the generated queryData and queryId

    \b
    Examples:
        - relayer parse-query --query-string "SpotPrice(eth,usd)"
        - relayer parse-query -q "CustomType(uint256 123, string 'hello', bool true)"
    """
    configure_logging(verbose=verbose, no_color=no_color)
    
    try:
        parser = QueryParser()
        query_info = parser.get_query_info(query_string)
        
        print(f"\n✅ Successfully parsed query string: {query_string}")
        print(f"📋 Query Type: {query_info['queryType']}")
        print(f"📝 Has Definition: {'Yes' if query_info['hasDefinition'] else 'No (using inline types)'}")
        
        # display parsed arguments
        arguments = query_info.get('arguments', [])
        if arguments:
            print(f"\n📝 Parsed Arguments:")
            for i, arg in enumerate(arguments, 1):
                name = arg['name']
                arg_type = arg['type']
                raw_value = arg['rawValue']
                
                # format the value nicely for display
                display_value = raw_value
                if arg_type == 'string' and ((raw_value.startswith("'") and raw_value.endswith("'")) or 
                                           (raw_value.startswith('"') and raw_value.endswith('"'))):
                    display_value = raw_value[1:-1]  # remove quotes for display
                
                print(f"   arg{i:<2} type: {arg_type:<10} value: {display_value}")
        else:
            print(f"\n📝 No arguments")
        
        print(f"\n🔑 Query ID: {query_info['queryId']}")
        print(f"📦 Query Data: {query_info['queryData']}")
        
        # show some additional useful info
        # remove 0x prefix for hex parsing, handling double prefix if present
        query_id_hex = query_info['queryId']
        if query_id_hex.startswith('0x0x'):
            query_id_hex = query_id_hex[3:]  # remove "0x0" to leave "x..."
        elif query_id_hex.startswith('0x'):
            query_id_hex = query_id_hex[2:]  # remove "0x"
            
        query_data_hex = query_info['queryData']
        if query_data_hex.startswith('0x'):
            query_data_hex = query_data_hex[2:]
        query_id_bytes = decode_hex(query_id_hex)
        query_data_bytes = decode_hex(query_data_hex)
        print(f"\n📊 Additional Info:")
        print(f"   Query ID length: {len(query_id_bytes)} bytes")
        print(f"   Query Data length: {len(query_data_bytes)} bytes")
        
    except Exception as e:
        logger.error(f"❌ Error parsing query string: {e}")
        exit(1)

if __name__ == '__main__':
    cli() 

@cli.command()
@add_logging_options
@click.option('--host', envvar='PRICE_SERVICE_HOST', default=None, help='Price service host (override)')
@click.option('--port', envvar='PRICE_SERVICE_PORT', type=int, default=None, help='Price service port (override)')
def price_service(host, port, verbose, no_color):
    """Run the HTTP price-service for batched provider fetching"""
    configure_logging(verbose=verbose, no_color=no_color)
    cfg_ref = os.environ.get('PRICE_SERVICE_CONFIG', 'price-service')
    try:
        run_price_service(cfg_ref, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("\nPrice service stopped by user.")
        exit(0)
    except Exception as e:
        logger.error(f"Error running price service: {e}")
        exit(1)