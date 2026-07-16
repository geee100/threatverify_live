import os
import requests

USDT_WALLET = os.getenv("USDT_WALLET")

def get_payment_message(amount, bug_id):
    return f"""💰 *LIVE PAYMENT: {amount} USDT* for Bug #{bug_id}

Send *EXACTLY* `{amount} USDT` to:
`{USDT_WALLET}`
Network: *TRC20 ONLY*

After sending, reply with:
`/txhash YOUR_TRANSACTION_HASH`
"""

def verify_usdt_tx(tx_hash):
    try:
        url = f"https://apilist.tronscan.org/api/transaction-info?hash={tx_hash}"
        r = requests.get(url, timeout=10).json()
        to_address = r.get('toAddress')
        amount = r.get('contractData',{}).get('amount', 0) / 1000000
        if to_address == USDT_WALLET and r.get('contractRet') == 'SUCCESS' and amount > 0:
            return "1", amount
    except:
        pass
    return None
