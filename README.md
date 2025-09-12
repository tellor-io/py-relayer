# Layer Relayer

This is a simple relayer that relays oracle data and validator set updates from tellor layer to evm chains.

## Setup

We assume you have python installed. Note, if you are running on ubuntu, see the additional requirements below.

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
python3 -m venv venv
source venv/bin/activate
```

4. Install the dependencies:
```bash
pip install -r requirements.txt
```

5. Install the package:
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

The relayer provides several commands through its CLI:

### Start Relaying
```bash
relayer relay --layer-test-user-address 0x39C93320776D7D9F75798fEF42C72433b718726d --data-bridge-address 0xc7670AeD260Ce55830D0766Eb4E5A04bE56979d3 --contract-type TestPriceFeedUser --sleep-time 900
```

### Relay Token Bridge Withdraw
```bash
relayer relay-bridge --data-bridge-address 0xa73Efa04476B45E5bBAa68A59f7Ee2A21e14FDD4 --token-bridge-address 0x6ac02F3887B358591b8B2D22CfB1F36Fa5843867 --withdraw-id 8
```

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
This relays data to the TellorDataBank contract based on a heartbeat and price change threshold.
```bash
relayer relay-threshold --query-string "SpotPrice(eth,usd)" --price-threshold 0.01 --data-bridge-address DATA_BRIDGE_CONTRACT_ADDRESS --layer-user-address LAYER_USER_CONTRACT_ADDRESS --layer-tx-creator-address LAYER_ADDRESS
```

### Threshold Relayer (Backup)
This acts as a backup for the threshold relayer so that if the primary relayer fails, the backup can take over. The backup relayer should use a slightly higher price threshold and heartbeat interval than the primary relayer.
```bash
relayer relay-threshold --backup --query-string "SpotPrice(eth,usd)" --price-threshold 0.01 --data-bridge-address DATA_BRIDGE_CONTRACT_ADDRESS --layer-user-address LAYER_USER_CONTRACT_ADDRESS --web3-provider WEB3_PROVIDER_URL --layer-swagger LAYER_SWAGGER_ENDPOINT --layer-rpc LAYER_RPC_ENDPOINT --layer-tx-creator-address LAYER_ADDRESS
```

To see all available options for each command:
```bash
relayer --help
relayer relay --help
relayer relay-threshold --help
```