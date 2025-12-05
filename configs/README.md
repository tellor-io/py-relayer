# Relayer Configuration System

This directory contains TOML configuration files for the relayer system. The new config system supports inheritance and allows running relayers with minimal command-line arguments.

## Usage

Run a relayer with a config:
```bash
# Run ETH/USD relayer with saga config
relayer --config saga/eth-usd relay-threshold

# Run BTC/USD relayer  
relayer --config saga/btc-usd relay-threshold
```

You only need to provide the ETH private key (via .env file or CLI):
```bash
# If not in .env, add it via CLI
relayer --config saga/eth-usd relay-threshold --eth-private-key "0x..."
```

## Structure

### Base Configs
- `saga-shared.toml` - Common settings for all Saga network feeds
- `saga/backup-template.toml` - Template for backup relayers with higher thresholds

### Feed Configs  
- `saga/eth-usd.toml` - Ethereum price feed
- `saga/btc-usd.toml` - Bitcoin price feed
- `saga/fbtc-usd.toml` - Fire Bitcoin price feed

### Price Service Config
- `price-service.toml` - Batching/caching price-service settings (server, providers, feeds)

## Config Format

Each config file can inherit from others using `extends`:

```toml
# Feed-specific config
extends = ["saga-shared"]  # Inherit common settings

[env]
FEED_NAME = "eth-usd"
COINGECKO_ID = "ethereum"

[commands.relay-threshold]
query_string = "SpotPrice(eth,usd)"
price_threshold = 0.01
price_api_url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
```

### Sections

- `[env]` - Environment variables set before command execution
- `[commands.<command>]` - Default values for CLI command options
- `extends` - List of parent configs to inherit from (deep-merged)

### Price Service Schema (price-service.toml)
```toml
[server]
host = "127.0.0.1"
port = 8787
cache_ttl_secs = 10

[providers.coingecko]
enabled = true
base_url = "https://api.coingecko.com/api/v3/simple/price"
rpm = 50

[providers.coinmarketcap]
enabled = false
base_url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
api_key = "${CMC_API_KEY}"
rpm = 30

[[feeds]]
name = "eth-usd"
quote = "usd"
coingecko_id = "ethereum"
coinmarketcap_id = "1027"
```

### Precedence

Values are resolved in this order (highest to lowest precedence):
1. CLI flags
2. Config file values  
3. .env file values
4. Hardcoded defaults

## Adding New Feeds

1. Create a new file: `configs/saga/<asset>-usd.toml`
2. Extend the shared config: `extends = ["saga-shared"]`
3. Set feed-specific values:
   - `FEED_NAME` and `COINGECKO_ID` in `[env]`
   - `query_string`, `price_threshold`, and `price_api_url` in `[commands.relay-threshold]`

Example:
```toml
extends = ["saga-shared"]

[env]
FEED_NAME = "usdc-usd"
COINGECKO_ID = "usd-coin"

[commands.relay-threshold]
query_string = "SpotPrice(usdc,usd)"
price_threshold = 0.005  # 0.5% for stablecoin
PRICE_SERVICE_URL = "http://127.0.0.1:8787"
FEED_NAME = "usdc-usd"
PRICE_AGGREGATION = "median"
```

## Backup Relayers

For backup relayers, extend the backup template:
```toml
extends = ["saga/backup-template"]

[commands.relay-threshold]
query_string = "SpotPrice(eth,usd)"
```

### Running the Price Service
```bash
# Using default config name 'price-service' which resolves to configs/price-service.toml
relayer price-service

# Or with an explicit config file
PRICE_SERVICE_CONFIG=configs/price-service.toml 
relayer price-service --host 0.0.0.0 --port 8787
```

This automatically uses higher thresholds and longer heartbeats suitable for backup operations.
