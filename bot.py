import os
import time
import threading
import requests
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler

# === CONFIG ===
TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME") 
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRONGRID_URL = "https://api.trongrid.io"
CHECK_INTERVAL = 60 # Check every 60 seconds

last_tx_seen = {} # Memory to prevent spam

# === GOOGLE SHEETS ===
def connect_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(eval(GOOGLE_CREDS_JSON), scopes=scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        print(f"Sheets Error: {e}")
        return None

sheet = connect_sheet()

# === TRON CHECKER ===
def get_last_usdt_tx(wallet_address):
    try:
        url = f"{TRONGRID_URL}/v1/accounts/{wallet_address}/transactions/trc20"
        params = {"contract_address": USDT_CONTRACT, "limit": 1, "only_to": "true"}
        headers = {"TRON-PRO-API-KEY": ""} # Free tier works without key
        r = requests.get(url, params=params, headers=headers, timeout=15)
        data = r.json()

        if "data" in data and len(data["data"]) > 0:
            tx = data["data"][0]
            amount = int(tx["value"]) / 1_000_000
            tx_id = tx["transaction_id"]
            timestamp = datetime.fromtimestamp(tx["block_timestamp"] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            return {"id": tx_id, "amount": amount, "from": tx["from"], "time": timestamp}
        return None
    except Exception as e:
        print(f"Tron API Error: {e}")
        return None

# === AUTO CHECKER - UPGRADED ===
def auto_check_loop(context: CallbackContext):
    while True:
        try:
            if sheet:
                records = sheet.get_all_records()
                for row in records:
                    wallet = row.get("Wallet")
                    user_id = str(row.get("UserID"))
                    if wallet and user_id:
                        tx = get_last_usdt_tx(wallet)
                        if tx:
                            # Only send if it's a NEW transaction
                            if last_tx_seen.get(wallet)!= tx["id"]:
                                last_tx_seen[wallet] = tx["id"]
                                msg = (
                                    f"🚨 *USDT PAYMENT RECEIVED!* 🚨\n\n"
                                    f"💰 *Amount:* `{tx['amount']}` USDT\n"
                                    f"👤 *From:* `{tx['from']}`\n"
                                    f"📅 *Time:* `{tx['time']}`\n"
                                    f"🔗 *TX:* `https://tronscan.org/#/transaction/{tx['id']}`"
                                )
                                context.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown', disable_web_page_preview=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Auto check crashed: {e}")
            time.sleep(CHECK_INTERVAL)

# === COMMANDS - NICE UI ===
def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("➕ Add Wallet", callback_data='add_help'), InlineKeyboardButton("📋 My Wallets", callback_data='list')],
        [InlineKeyboardButton("🔍 Check Wallet", callback_data='check_help')],
        [InlineKeyboardButton("📊 Open Google Sheet", url=f"https://docs.google.com/spreadsheets/d/{sheet.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "👋 *Welcome to Pro USDT Tracker Bot*\n\n"
        "✅ *Status:* Online 24/7\n"
        "✅ *Auto Check:* Every 60 seconds\n"
        "✅ *Sheets:* Connected\n"
        "*Commands:*\n"
        "`/add <wallet>` - Track new wallet\n"
        "`/check <wallet>` - Check last payment\n"
        "`/list` - See all your wallets\n"
        "`/delete <wallet>` - Stop tracking",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == 'list':
        list_wallets(update, context)
    elif query.data == 'add_help':
        query.edit_message_text("Send: `/add TRON_WALLET_ADDRESS`", parse_mode='Markdown')
    elif query.data == 'check_help':
        query.edit_message_text("Send: `/check TRON_WALLET_ADDRESS`", parse_mode='Markdown')

def add_wallet(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("❌ Usage: `/add TQxyz...`", parse_mode='Markdown')
        return
    wallet = context.args[0]
    user_id = update.effective_user.id
    if sheet:
        sheet.append_row([user_id, wallet, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    update.message.reply_text(f"✅ *Wallet Added!*\n`{wallet}`\n\nI will now auto-check this wallet every 60s", parse_mode='Markdown')

def check(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("❌ Usage: `/check TQxyz...`", parse_mode='Markdown')
        return
    wallet = context.args[0]
    msg = context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ Checking blockchain...")
    tx = get_last_usdt_tx(wallet)
    if tx:
        msg.edit_text(
            f"🔍 *Last USDT Transaction*\n\n"
            f"💰 *Amount:* `{tx['amount']}` USDT\n"
            f"👤 *From:* `{tx['from']}`\n"
            f"📅 *Time:* `{tx['time']}`\n"
            f"🔗 [View on Tronscan](https://tronscan.org/#/transaction/{tx['id']})",
            parse_mode='Markdown', disable_web_page_preview=True
        )
    else:
        msg.edit_text("😕 No USDT transactions found for this wallet.")

def list_wallets(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if sheet:
        records = sheet.get_all_records()
        wallets = [f"`{r['Wallet']}`" for r in records if str(r["UserID"]) == user_id]
        if wallets:
            msg = "📋 *Your Tracked Wallets:*\n\n" + "\n".join(wallets)
        else:
            msg = "You have no wallets added. Use `/add <wallet>`"
        update.message.reply_text(msg, parse_mode='Markdown')

def delete_wallet(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("❌ Usage: `/delete TQxyz...`", parse_mode='Markdown')
        return
    wallet = context.args[0]
    user_id = str(update.effective_user.id)
    # This is basic. For full delete you need to find row and delete
    update.message.reply_text(f"⚠️ To delete `{wallet}`, remove it from Google Sheet manually.", parse_mode='Markdown')

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_wallet))
    dp.add_handler(CommandHandler("check", check))
    dp.add_handler(CommandHandler("list", list_wallets))
    dp.add_handler(CommandHandler("delete", delete_wallet))
    dp.add_handler(CallbackQueryHandler(button_handler))

    thread = threading.Thread(target=auto_check_loop, args=(updater,), daemon=True)
    thread.start()

    print("🚀 Pro Bot Running. Auto USDT Check Enabled.")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
