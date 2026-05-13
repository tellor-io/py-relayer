# Layer Relayer

Relayers for Tellor Layer that:
- relay oracle values from Layer to EVM (`relay-threshold`)
- relay bridge withdrawals from Layer to EVM (`relay-bridge`)
- sync validator sets (`relay-valset`)
- manage bridge contract lifecycle (`init`, `reset`)

This repo is config-driven via `configs/` and is operated with `telliot-feeds` as the price source.

## Setup

1. Create and activate a Python virtual environment:
```bash
python3.12 -m venv venv3.12
source venv3.12/bin/activate
```

2. Install dependencies and the CLI:
```bash
pip install -r requirements.txt
pip install -e .
```

3. Copy `.env.example` to `.env` and fill in required secrets:
```bash
cp .env.example .env
```

CLI flags override config values, and config values override `.env`.

## EVM Signer Configuration

Prefer encrypted `chained-accounts` keystores for EVM transaction signing. The relayer can use the same keystores that Telliot uses, stored by `chained-accounts` under `~/.chained_accounts/<name>.json`.

Create or inspect relayer keystores with:

```bash
relayer account add relayer-sepolia 0xYOUR_PRIVATE_KEY 11155111
relayer account find --name relayer-sepolia
relayer account key relayer-sepolia
```

Configure a keystore signer with:

```bash
export EVM_ACCOUNT_NAME="relayer-sepolia"
export EVM_KEYSTORE_PASSWORD="..."  # prefer systemd/secret-manager injection for services
```

You can also set `EVM_ACCOUNT_ADDRESS` as an extra safety check, or omit `EVM_ACCOUNT_NAME` and let the relayer select the only keystore matching the connected EVM chain. If multiple accounts match, the relayer will require `EVM_ACCOUNT_NAME`.

`ETH_PRIVATE_KEY` and `--eth-private-key` remain supported as a legacy fallback, but production relayers should avoid storing raw private keys in `.env`.

## Commands In Use

The commands currently used in operations are:
- `account`
- `init`
- `parse-query`
- `relay-bridge`
- `relay-threshold`
- `relay-valset`
- `reset`

## Config-First Workflow

The relayer relies heavily on the config system:
- Config files live in `configs/`
- Inheritance uses `extends = [...]`
- `[env]` sets environment variables
- `[commands.<command>]` sets per-command defaults

You can pass `--config` as:
- a config name (`sepolia-shared`)
- a nested config name (`sepolia/eth-usd`)
- or a path (`configs/sepolia/eth-usd.toml`)

### Config example

```toml
extends = ["sepolia-shared"]

[env]
FEED_NAME = "eth-usd"
PRICE_SOURCE = "telliot-feeds"

[commands.relay-threshold]
query_string = "SpotPrice(eth,usd)"
price_threshold = 0.02
```

## Relay Examples (Current)

```bash
relayer --config sepolia/eth-usd relay-threshold
```

```bash
relayer --config sepolia-shared relay-bridge --withdraw-id 1
```

## Command Quick Reference

### `relay-threshold`

Primary oracle relayer (heartbeat + threshold logic), typically run with feed configs such as `sepolia/eth-usd`.

```bash
relayer --config sepolia/eth-usd relay-threshold
```

### `relay-bridge`

Relays a withdrawal from Layer to EVM.

```bash
relayer --config sepolia-shared relay-bridge --withdraw-id 1
```

### `relay-valset`

Relays validator set updates.

```bash
relayer --config sepolia-shared relay-valset
```

### `init`

Initializes the data bridge contract (one-time deployer action).

```bash
relayer --config sepolia-shared init
```

### `reset`

Guardian reset for stale validator set scenarios.

```bash
relayer --config sepolia-shared reset
```

### `parse-query`

Parses a query string and prints query metadata (`queryId`, `queryData`, parsed args).

```bash
relayer parse-query --query-string "SpotPrice(eth,usd)"
```

## Notes

- `price-service` is not part of the active operational workflow.
- Use `telliot-feeds` via config (`PRICE_SOURCE=telliot-feeds`) for threshold relaying.
- See `configs/README.md` for additional config examples.