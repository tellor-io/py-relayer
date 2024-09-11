from msg_tip import MsgTip
from lcd_client import LCDClient
from terra_sdk.key.mnemonic import MnemonicKey
from terra_sdk.client.lcd.api.tx import CreateTxOptions

# # hardcode inputs
mnemonic = "circle foster million antenna island fly judge item predict giant staff brave stem nerve any tissue vibrant immune sad inquiry problem finish runway lumber"
layer_endpoint = "https://tellorlayer.com"
chain_id = "layertest-1"
query_data = "0x00000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000080000000000000000000000000000000000000000000000000000000000000000953706f745072696365000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000003657468000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000037573640000000000000000000000000000000000000000000000000000000000"
tip_amount = "100"

# creat client and wallet
client = LCDClient(url=layer_endpoint, chain_id=chain_id)
key = MnemonicKey(mnemonic=mnemonic)
wallet = client.wallet(key)

# create tip msg
msg = MsgTip(
    sender=wallet.key.acc.address,
    query_data=query_data,
    tip_amount=tip_amount
)
options = CreateTxOptions(msgs=[msg], gas=1000)

tx = wallet.create_and_sign_tx(options)



# # query the chain
# layer = LCDClient(chain_id="layertest-1", url="https://tellorlayer.com")

# # get latest block
# block = layer.tendermint.block_info()
# print("latest block: ", block)
