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
relayer relay --query-id 0x83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992 --sleep-time 600
```

### Initialize Blobstream
```bash
relayer init
```

### Reset Blobstream
```bash
relayer reset
```

### Update Oracle Data
```bash
relayer update --query-id 0x83a7f3d48786ac2667503a61e8c415438ed2922eb86a2906e4ee66d9a2ce4992
```

For security reasons, we recommend storing sensitive information (like your Ethereum private key) in the .env file rather than passing them as command line arguments. Other configuration options can be passed either through the CLI or set in your .env file.

To see all available options for each command:
```bash
relayer --help
relayer relay --help
```