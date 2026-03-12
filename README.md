# Layer Relayer

Relayers for Tellor Layer that synchronize validator sets, relay oracle data to EVM chains, and relay token-bridge withdrawals. Includes a threshold relayer driven by heartbeat and external price-change thresholds, and a shared HTTP price-service supporting batched provider queries.

## Setup

We assume you have Python installed (this repo targets **Python 3.12**). Note, if you are running on ubuntu, see the additional requirements below.

1. Clone the repo:
```bash
git clone https://github.com/tellor-io/py-relayer.git
```

2. Navigate to the repository directory:
```bash
cd py-relayer
```

3. Create a virtual environment:
```bash
python3.12 -m venv venv3.12
source venv3.12/bin/activate
```

4. Install the dependencies:
```bash
pip install -r requirements.txt
```

5. Install the relayer CLI in editable mode (provides the `relayer` command):
```bash
pip install -e .
```

6. Copy the .env.example file to .env and set the appropriate environment variables:
```bash
cp .env.example .env
```

All .env variables can alternatively be set through the CLI. We recommend setting your ethereum private key in the .env file for security reasons. For convenience, you should set any parameters which tend to remain constant across runs in the .env file. CLI arguments will override .env variables.

### Additional Requirements for Ubuntu

If you are running the relayer on ubuntu, you may need to install additional tools:

```bash
sudo apt update
sudo apt install build-essential python3-dev
```

After installing these dependencies, proceed with the setup instructions above.

## Usage

The CLI provides the following commands:

### Simple Oracle Relayer (interval-based)
```bash
relayer relay --query-string "SpotPrice(eth,usd)" \
  --data-bridge-address <DATA_BRIDGE> \
  --layer-user-address <USER_CONTRACT> \
  --web3-provider <RPC> --layer-swagger <LAYER_API> --layer-rpc <LAYER_RPC> \
  --sleep-time 900 --fixed-interval
```

### Token Bridge Withdraw Relayer
By default, `relay-bridge` uses the **TokenBridge V2** contract (`TRBBridgeV2` query type) and calls `withdrawFromLayer`.

```bash
relayer relay-bridge --data-bridge-address <DATA_BRIDGE> --token-bridge-address <TOKEN_BRIDGE_V2> --withdraw-id 8 ...
```

- **`--legacy`**: Relay to the legacy TokenBridge V1 (`TRBBridge` query type). Requires `TOKEN_BRIDGE_LEGACY_ADDRESS` in config or `--token-bridge-legacy-address`.
- **`--reverify`**: Call TokenBridge V2 `reverifyExtraWithdraw` (e.g. after bridge pause/unpause) for a withdraw that has pending amount to claim.

Config: set `TOKEN_BRIDGE_LEGACY_ADDRESS` in your env/config when using `--legacy`.

### Initialize Data Bridge
This calls the data bridge `init` function to set the initial validator set. The `init` function can only be called by the contract deployer, and only once.
```bash
relayer init
```

### Reset Data Bridge
This allows the bridge guardian to reset the validator set, if and only if the validator set is stale (21 days old).
```bash
relayer reset
```

### Threshold Relayer (Primary)
Heartbeat + price-threshold driven relayer to `TellorDataBank`. Uses external price(s) from the price-service (if configured), else falls back to a single `PRICE_API_URL`, else Layer aggregate.
```bash
relayer relay-threshold --query-string "SpotPrice(eth,usd)" --price-threshold 0.01 \
  --data-bridge-address <DATA_BRIDGE> --layer-user-address <DATABANK> \
  --web3-provider <RPC> --layer-swagger <LAYER_API> --layer-rpc <LAYER_RPC> \
  --layer-tx-creator-address <LAYER_ADDR>
```

### Threshold Relayer (Backup)
Conservative gates and higher thresholds/heartbeat.
```bash
relayer relay-threshold --backup --query-string "SpotPrice(eth,usd)" --price-threshold 0.015 \
  --data-bridge-address <DATA_BRIDGE> --layer-user-address <DATABANK> \
  --web3-provider <RPC> --layer-swagger <LAYER_API> --layer-rpc <LAYER_RPC> \
  --layer-tx-creator-address <LAYER_ADDR>
```

### Validator Set Relayer
Sync the EVM bridge validator set to Layer periodically (no oracle relay):
```bash
relayer relay-valset --data-bridge-address <DATA_BRIDGE> \
  --web3-provider <RPC> --layer-swagger <LAYER_API> --layer-rpc <LAYER_RPC> \
  --sleep-time 900 --fixed-interval
```

### Price Service
Run a shared HTTP price-service that batches/caches external provider calls (CoinGecko, CoinMarketCap, CoinPaprika, Coinbase, Curve price API):
```bash
# defaults to configs/price-service.toml
relayer price-service

# or explicit
PRICE_SERVICE_CONFIG=configs/price-service.toml ./venv3.12/bin/python -m src.cli price-service --host 0.0.0.0 --port 8787
```

Endpoints:
- GET /price?feed=eth-usd[&agg=median&required=1]
- GET /batch?feeds=eth-usd,btc-usd[&agg=trimmed_mean:0.1]

### Config System (TOML)
Configs live under `configs/`, support inheritance via `extends`, and provide both environment variables (`[env]`) and per-command defaults (`[commands.<name>]`). Example:
```toml
extends = ["saga-shared"]

[env]
FEED_NAME = "eth-usd"
PRICE_SERVICE_URL = "http://127.0.0.1:8787"

[commands.relay-threshold]
query_string = "SpotPrice(eth,usd)"
price_threshold = 0.01
```

Per-network shared configs: `saga-shared.toml`, `sepolia-shared.toml`. Feed configs: `configs/<network>/<feed>.toml` (templates included for ETH/BTC/USDC/USDT/TBTC/wstETH/rETH/stATOM).

When using configs:
```bash
relayer --config saga/eth-usd relay-threshold --eth-private-key 0x...
```

### Help
```bash
relayer --help
relayer relay --help
relayer relay-threshold --help
relayer relay-bridge --help
relayer relay-valset --help
```