import requests

USDT_WALLET = "TDMGiXCJNqcjkXrp6jvoph9G5NSy73R3gb" # CHANGE TO YOUR WALLET

def get_payment_message(amount, bug_id):
    return f"""💰 *LIVE PAYMENT: {amount} USDT* for Bug #{bug_id}

Send *EXACTLY* `{amount} USDT` to:
`{USDT_WALLET}`
Network: *TRC20 ONLY*

After sending, reply with:
`/txhash YOUR_TRANSACTION_HASH`

Bot will auto-verify in 2 minutes and mark as PAID.
"""

def verify_usdt_tx(tx_hash):
    try:
        url = f"https://apilist.tronscan.org/api/transaction-info?hash={tx_hash}"
        r = requests.get(url, timeout=10).json()

        to_address = r.get('toAddress')
        amount = r.get('contractData',{}).get('amount', 0) / 1000000 # USDT has 6 decimals

        if to_address == USDT_WALLET and r.get('contractRet') == 'SUCCESS' and amount > 0:
            # For now we return bug_id 1. Later we can add memo
            bug_id = "1"
            return bug_id, amount
    except:
        pass
    return None
