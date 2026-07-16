import os
import time
import threading
import requests
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext

# === CONFIG ===
TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# USDT TRC20 Contract Address
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRONGRID_URL = "https://api.trongrid.io"

# === GOOGLE SHEETS SETUP ===
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(eval(GOOGLE_CREDS_JSON), scopes=scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

sheet = connect_sheet()

# === TRON USDT CHECK FUNCTION ===
def get_last_usdt_tx(wallet_address):
    try:
        url = f"{TRONGRID_URL}/v1/accounts/{wallet_address}/transactions/trc20"
        params = {"contract_address": USDT_CONTRACT, "limit": 1, "only_to": "true"}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if "data" in data and len(data["data"]) > 0:
            tx = data["data"][0]
            amount = int(tx["value"]) / 1_000_000
            return {"amount": amount, "from": tx["from"], "time": tx["block_timestamp"]}
        return None
    except:
        return None

# === AUTO CHECK LOOP ===
def auto_check_loop(context: CallbackContext):
    while True:
        try:
            records = sheet.get_all_records()
            for row in records:
                wallet = row.get("Wallet")
                user_id = row.get("UserID")
                if wallet and user_id:
                    tx = get_last_usdt_tx(wallet)
                    if tx:
                        msg = f"💰 *New USDT Received!*\n\nAmount: `{tx['amount']}` USDT\nFrom: `{tx['from']}`"
                        context.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
            time.sleep(60) # Check every 60 seconds
        except Exception as e:
            print(f"Auto check error: {e}")
            time.sleep(60)

# === TELEGRAM COMMANDS - NICE DESIGN ===
def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🔍 Check Wallet", callback_data='check')],
        [InlineKeyboardButton("📊 My Sheet", url=f"https://docs.google.com/spreadsheets/d/{sheet.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "👋 *Pro USDT Bot is LIVE*\n\n"
        "Auto USDT Check: *ENABLED*\n"
        "Google Sheets: *CONNECTED*\n\n"
        "Commands:\n"
        "`/add <wallet>` - Add wallet to track\n"
        "`/check <wallet>` - Check last USDT\n"
        "`/list` - List all tracked wallets",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def add_wallet(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("Usage: `/add TRON_WALLET_ADDRESS`", parse_mode='Markdown')
        return
    wallet = context.args[0]
    user_id = update.effective_user.id
    sheet.append_row([user_id, wallet])
    update.message.reply_text(f"✅ Wallet `{wallet}` added to tracking!", parse_mode='Markdown')

def check(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("Usage: `/check TRON_WALLET_ADDRESS`", parse_mode='Markdown')
        return
    wallet = context.args[0]
    tx = get_last_usdt_tx(wallet)
    if tx:
        update.message.reply_text(
            f"🔍 *Last USDT Tx*\n\nAmount: `{tx['amount']}` USDT\nFrom: `{tx['from']}`",
            parse_mode='Markdown'
        )
    else:
        update.message.reply_text("No USDT transactions found for this wallet.")

def list_wallets(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    records = sheet.get_all_records()
    wallets = [r["Wallet"] for r in records if str(r["UserID"]) == str(user_id)]
    if wallets:
        msg = "📋 *Your Tracked Wallets:*\n\n" + "\n".join([f"`{w}`" for w in wallets])
    else:
        msg = "You have no wallets added yet. Use `/add <wallet>`"
    update.message.reply_text(msg, parse_mode='Markdown')

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_wallet))
    dp.add_handler(CommandHandler("check", check))
    dp.add_handler(CommandHandler("list", list_wallets))

    # Start auto check in background thread
    thread = threading.Thread(target=auto_check_loop, args=(updater,), daemon=True)
    thread.start()

    print("Pro Bot Running. Auto USDT Check Enabled.")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
