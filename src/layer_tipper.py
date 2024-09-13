from msg_tip import MsgTip
from lcd_client import LCDClient
from terra_sdk.key.raw import RawKey
from terra_sdk.client.lcd.api.tx import CreateTxOptions

# hardcode inputs
PRIVATE_KEY = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
# LAYER_ENDPOINT = "https://tellor-testnet.rpc.nodex.one"
LAYER_ENDPOINT = "https://layer.itsaboomerang.net/"
CHAIN_ID = "layertest-1"
QUERY_DATA = "0x00000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000080000000000000000000000000000000000000000000000000000000000000000953706f745072696365000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000003657468000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000037573640000000000000000000000000000000000000000000000000000000000"
TIP_AMOUNT = "100loya"

def tip():
    # creat client and wallet
    print("layer_tipper: Creating client and wallet...")
    client = LCDClient(url=LAYER_ENDPOINT, chain_id=CHAIN_ID)
    print("layer_tipper: Creating key...")
    key = RawKey.from_hex(PRIVATE_KEY)
    print("layer_tipper: Creating wallet...")
    wallet = client.wallet(key)

    # create tip msg
    print("layer_tipper: Creating tip msg...")
    msg = MsgTip(
        sender=wallet.key.acc.address,
        query_data=QUERY_DATA,
        tip_amount=TIP_AMOUNT
    )
    print("layer_tipper: Creating tx options...")
    options = CreateTxOptions(msgs=[msg], gas=1000)
    print("layer_tipper: Creating tx...")
    
    try:
        print("layer_tipper: Creating tx...")
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

sanity_check()
