import requests
import time

ASSET_STRING = "ethereum"
THRESHOLD = 0.0001
INTERVAL = 20
cached_price = 0
max_change = 0

def query_coingecko_api(currency: str) -> tuple[str, Exception]:
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={currency}&vs_currencies=usd"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        ethereum_price = data["ethereum"]["usd"]
        return ethereum_price, None
    except requests.exceptions.RequestException as e:
        print(f"Error querying Coingecko API: {e}")
        return None, e

def check_price_change(currency: str, threshold: float) -> tuple[bool, Exception]:
    print(f"threshold_trigger: checking price change")
    global cached_price
    old_price = cached_price
    print(f"threshold_trigger: cached price: {old_price}")
    new_price, err = query_coingecko_api(currency)
    if err:
        return False, err
    print(f"threshold_trigger: new price: {new_price}")
    if new_price == 0:
        return False, Exception("Price is 0")
    cached_price = new_price
    if old_price == 0:
        return False, None
    price_change = (float(new_price) - float(old_price)) / float(old_price)
    print(f"threshold_trigger: price change: {price_change}")
    global max_change
    if abs(price_change) > max_change:
        max_change = abs(price_change)
        print(f"threshold_trigger: max change: {max_change}")
    if abs(price_change) >= threshold:
        return True, None
    return False, None

