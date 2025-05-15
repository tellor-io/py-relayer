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

The "email" section of the .env file is optional. If you want to receive emails when layer is down, input your gmail username and password. We recommend using an [app password](https://support.google.com/accounts/answer/185833?hl=en) for your gmail account.

Other than the email section, all .env variables can alternatively be set through the CLI. We recommend setting your ethereum private key in the .env file for security reasons. For convenience, you should set any parameters which tend to remain constant across runs in the .env file. CLI arguments will override .env variables.

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

### Update Oracle Data Once
```bash
relayer update --query-id 0x83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992
```

### Relay Token Bridge Withdraw
```bash
relayer relay-bridge --data-bridge-address 0xa73Efa04476B45E5bBAa68A59f7Ee2A21e14FDD4 --token-bridge-address 0x6ac02F3887B358591b8B2D22CfB1F36Fa5843867 --withdraw-id 8
```

### Initialize Data Bridge
```bash
relayer init
```

### Reset Data Bridge
```bash
relayer reset
```




To see all available options for each command:
```bash
relayer --help
relayer relay --help
```