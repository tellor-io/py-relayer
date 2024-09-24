from msg_tip import MsgTip
from terra_sdk.core.bank import MsgSend
from lcd_client import LCDClient
from raw_key import RawKey
from terra_sdk.client.lcd.api.tx import CreateTxOptions
from terra_sdk.core.fee import Fee
from terra_sdk.core.coin import Coin
# hardcode inputs
PRIVATE_KEY = "4f88ba20a4cdcc875f32b15338ee62bc6a7372fe6241d1a489b52864b39fd82c"
# LAYER_ENDPOINT = "https://tellor-testnet.rpc.nodex.one"
LAYER_ENDPOINT = "http://localhost:1317"
CHAIN_ID = "layertest-2"
QUERY_DATA = "00000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000080000000000000000000000000000000000000000000000000000000000000000953706f745072696365000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000003657468000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000037573640000000000000000000000000000000000000000000000000000000000"
TIP_AMOUNT = "100loya"

def tip():
    # creat client and wallet
    print("layer_tipper: Creating client and wallet...")
    client = LCDClient(url=LAYER_ENDPOINT, chain_id=CHAIN_ID)
    print("layer_tipper: Creating key...")
    key = RawKey.from_hex(PRIVATE_KEY)
    print("layer_tipper: Creating wallet...")
    wallet = client.wallet(key)
    wallet_address = wallet.key.acc_address
    print("layer_tipper: Wallet address: ", wallet_address)

    # create tip msg
    print("layer_tipper: Creating tip msg...")
    msg = MsgTip(
        tipper=wallet.key.acc_address,
        query_data=bytes.fromhex(QUERY_DATA),
        amount=Coin.from_str(TIP_AMOUNT)
    )
    print("layer_tipper: Creating tx options...")
    options = CreateTxOptions(
        msgs=[msg],
        memo="test tip tx",
        fee=Fee(200000, "500loya"),
    )
    
    try:
        print("layer_tipper: Creating unsigned tx...")
        unsigned_tx = wallet.create_tx(options)
        print(f"layer_tipper: Unsigned tx: {unsigned_tx}")
        print("layer_tipper: Creating and signing tx...")
        tx = wallet.create_and_sign_tx(options)
        print("layer_tipper: Submitting tx...")
        tx_response = client.tx.broadcast_sync(tx)
        print("layer_tipper: Tx submitted...")
        print("layer_tipper: Tx response...")
        print(tx_response)
    except Exception as e:
        print("layer_tipper: Error submitting tx...")
        print(e)

def send():
    # creat client and wallet
    print("layer_tipper: Creating client and wallet...")
    client = LCDClient(url=LAYER_ENDPOINT, chain_id=CHAIN_ID)
    print("layer_tipper: Creating key...")
    key = RawKey.from_hex(PRIVATE_KEY)
    print("layer_tipper: Creating wallet...")
    wallet = client.wallet(key)
    wallet_address = wallet.key.acc_address
    print("layer_tipper: Wallet address: ", wallet_address)

    # create bank send msg
    msg = MsgSend(
        wallet.key.acc_address,
        "tellor1fyncvqhqpx9m9axw8pk3ffzk8naede4dqte7aa",
        "123loya"
    )
    options = CreateTxOptions(
        msgs=[msg],
        memo="test send tx",
        fee=Fee(200000, "500loya"),
    )
    try:
        print("layer_tipper: Creating unsigned tx...")
        unsigned_tx = wallet.create_tx(options)
        print(f"layer_tipper: Unsigned tx: {unsigned_tx}")
        print("layer_tipper: Creating and signing tx...")
        tx = wallet.create_and_sign_tx(options)
        print("layer_tipper: Submitting tx...")
        tx_response = client.tx.broadcast_sync(tx)
        print("layer_tipper: Tx submitted...")
        print("layer_tipper: Tx response...")
        print(tx_response)
    except Exception as e:
        print("layer_tipper: Error submitting tx...")
        print(e)

def sanity_check():
    # # query the chain
    layer = LCDClient(chain_id=CHAIN_ID, url=LAYER_ENDPOINT)

    # # get latest block
    block = layer.tendermint.block_info()
    print("latest block: ", block)

def total_supply():
    layer = LCDClient(chain_id=CHAIN_ID, url=LAYER_ENDPOINT)
    total_supply = layer.bank.total()
    print("total supply: ", total_supply)

tip()