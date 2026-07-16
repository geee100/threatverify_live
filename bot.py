import os
import time
import threading
import requests
import gspread
import asyncio
from datetime import datetime
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ========== CONFIG ==========
TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME") 
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t" # USDT TRC20
TRONGRID_URL = "https://api.trongrid.io"

# ========== GOOGLE SHEETS ==========
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(eval(GOOGLE_CREDS_JSON), scopes=scope)
    client = gspread.authorize(creds)
    try:
        sheet = client.open(SHEET_NAME).sheet1
    except:
        # Create sheet if doesn't exist
        sh = client.create(SHEET_NAME)
        sheet = sh.sheet1
        sheet.append_row(["UserID", "Wallet", "DateAdded"])
    return sheet

sheet = connect_sheet()
last_tx_seen = {}

# ========== TRON/USDT CHECKER ==========
def get_last_usdt_tx(wallet_address):
    try:
        url = f"{TRONGRID_URL}/v1/accounts/{wallet_address}/transactions/trc20"
        params = {"contract_address": USDT_CONTRACT, "limit": 1, "only_to": "true"}
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "data" in data and len(data["data"]) > 0:
            tx = data["data"][0]
            amount = int(tx["value"]) / 1_000_000 # USDT has 6 decimals
            tx_id = tx["transaction_id"]
            timestamp = datetime.fromtimestamp(tx["block_timestamp"]/1000).strftime('%Y-%m-%d %H:%M:%S')
            return {"id": tx_id, "amount": amount, "from": tx["from"], "time": timestamp}
        return None
    except Exception as e:
        print(f"TRON API Error: {e}")
        return None

# ========== AUTO CHECKER LOOP ==========
async def auto_check_loop(app):
    print("🔄 Auto USDT Checker Started...")
    while True:
        try:
            records = sheet.get_all_records()
            for row in records:
                wallet = row.get("Wallet")
                user_id = str(row.get("UserID"))
                if wallet and user_id:
                    tx = get_last_usdt_tx(wallet)
                    if tx and last_tx_seen.get(wallet)!= tx["id"]:
                        last_tx_seen[wallet] = tx["id"]
                        msg = f"🚨 *USDT RECEIVED!* 🚨\n\n" \
                              f"💰 *Amount:* `{tx['amount']}` USDT\n" \
                              f"👤 *From:* `{tx['from']}`\n" \
                              f"🕒 *Time:* `{tx['time']}`\n" \
                              f"🔗 *TX:* `https://tronscan.org/#/transaction/{tx['id']}`"
                        await app.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')
            await asyncio.sleep(60) # Check every 60 seconds
        except Exception as e:
            print(f"Auto check error: {e}")
            await asyncio.sleep(60)

# ========== TELEGRAM COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Add Wallet", callback_data='add')],
        [InlineKeyboardButton("🔍 Check Wallet", callback_data='check')],
        [InlineKeyboardButton("📋 My Wallets", callback_data='list')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 *Welcome to Pro USDT Tracker Bot*\n\n"
        "I will automatically notify you when USDT is sent to your wallets.\n\n"
        "*Commands:*\n"
        "`/add <wallet>` - Add wallet to track\n"
        "`/check <wallet>` - Check last USDT\n"
        "`/list` - See your wallets\n"
        "`/remove <wallet>` - Remove wallet",
        parse_mode='Markdown', reply_markup=reply_markup
    )

async def add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) == 0:
        await update.message.reply_text("❌ Usage: `/add TYourWalletAddress`", parse_mode='Markdown')
        return
    
    wallet = context.args[0]
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sheet.append_row([user_id, wallet, date])
    await update.message.reply_text(f"✅ *Wallet Added!*\n\n`{wallet}`\n\nI will now auto-check this wallet every 1 minute.", parse_mode='Markdown')

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ Usage: `/check TYourWalletAddress`", parse_mode='Markdown')
        return
    
    wallet = context.args[0]
    await update.message.reply_text("🔍 Checking blockchain... please wait")
    tx = get_last_usdt_tx(wallet)
    if tx:
        msg = f"✅ *Last USDT Transaction*\n\n" \
              f"💰 *Amount:* `{tx['amount']}` USDT\n" \
              f"👤 *From:* `{tx['from']}`\n" \
              f"🕒 *Time:* `{tx['time']}`\n" \
              f"🔗 *TX:* `https://tronscan.org/#/transaction/{tx['id']}`"
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text("⚠️ No USDT TRC20 transactions found for this wallet.")

async def list_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    records = sheet.get_all_records()
    user_wallets = [row['Wallet'] for row in records if str(row['UserID']) == user_id]
    
    if not user_wallets:
        await update.message.reply_text("📭 You have no wallets added yet. Use `/add <wallet>`")
        return
    
    msg = "📋 *Your Tracked Wallets:*\n\n"
    for i, w in enumerate(user_wallets, 1):
        msg += f"{i}. `{w}`\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ Usage: `/remove TYourWalletAddress`", parse_mode='Markdown')
        return
    
    wallet = context.args[0]
    user_id = str(update.effective_user.id)
    records = sheet.get_all_records()
    
    for i, row in enumerate(records):
        if str(row['UserID']) == user_id and row['Wallet'] == wallet:
            sheet.delete_rows(i + 2) # +2 because header + 1 index
            await update.message.reply_text(f"🗑️ Wallet removed: `{wallet}`", parse_mode='Markdown')
            return
    await update.message.reply_text("❌ Wallet not found in your list.")

# ========== MAIN ==========
def main():
    if not TOKEN:
        print("❌ ERROR: BOT_TOKEN not set in Environment Variables")
        return
        
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_wallet))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("list", list_wallets))
    app.add_handler(CommandHandler("remove", remove_wallet))
    
    # Start auto checker in background
    asyncio.create_task(auto_check_loop(app))
    
    print("🚀 Pro Bot Running. Auto USDT Check Enabled.")
    app.run_polling()

if __name__ == '__main__':
    main()
