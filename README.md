# Layer Relayer

This is a simple relayer that relays oracle data and validator set updates from tellor layer to evm chains.

## Setup

We assume you have python installed. 

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

5. Copy the .env.example file to .env and set the appropriate environment variables:
```bash
cp .env.example .env
```

The "email" section of the .env file is optional. If you want to receive emails when layer is down, input your gmail username and password. We recommend using an [app password](https://support.google.com/accounts/answer/185833?hl=en) for your gmail account.


## Run the Relayer

```bash
python3 src/relayer.py
```