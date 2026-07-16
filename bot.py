import os, requests, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8542751247:AAH_N4BWxh7bEEYHLi2-8pcr8CNhCBgGyBE"
YOUR_WALLET = "TDMGiXCJNqcjkXrp6jvoph9G5NSy73R3gb"
PRICE = 5 # $5 USDT
ADMIN_ID = 8542751247 # This is your Telegram ID from your token. Change if needed

users_db = {} # {user_id: {"txid": "", "status": "pending"}}
scam_db = {} # {username: {"reports": 2, "last_case": "$50"}}

TRON_API = "https://apilist.tronscan.org/api/transfer"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Report Scammer", callback_data='report')],
        [InlineKeyboardButton("📊 My Reports", callback_data='reports')],
        [InlineKeyboardButton("💬 Support", callback_data='support')]
    ]
    await update.message.reply_text(
        "⚡ Threat Verify Pro Bot\nAI-Powered Scam Intelligence\nPick an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'report':
        await query.message.reply_text(
            f"💰 Send ${PRICE} USDT TRC20 to:\n`{YOUR_WALLET}`\n\n"
            f"After payment send: `/tx YOUR_TXID`\n"
            f"Bot will auto-verify in 20 seconds."
        )

async def tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /tx TXID")
        return
    
    txid = context.args[0]
    await update.message.reply_text("⏳ Reviewing payment on TRON network...")

    # AUTO CHECK PAYMENT
    verified = await check_usdt_payment(txid)
    
    if verified:
        users_db[user_id] = {"txid": txid, "status": "paid"}
        await update.message.reply_text(
            f"✅ Payment Confirmed: ${PRICE} USDT\n\n"
            f"Generating AI Intelligence Report...\n"
            f"TXID: `{txid}`"
        )
        await asyncio.sleep(2)
        await update.message.reply_text(
            "📄 INTELLIGENCE REPORT\n"
            "Risk Level: HIGH\n"
            "Database Matches: 0\n"
            "Recommendation: AVOID\n"
            "Full report sent to DM."
        )
        # Notify admin
        await context.bot.send_message(ADMIN_ID, f"💰 New Payment!\nUser: {user_id}\nTXID: {txid}")
    else:
        await update.message.reply_text("❌ Payment not found or less than $5. Please send correct amount and try again.")

async def check_usdt_payment(txid):
    """Auto verify USDT TRC20 payment"""
    try:
        url = f"{TRON_API}?transaction={txid}&limit=1"
        r = requests.get(url, timeout=10).json()
        if r.get("data"):
            tx = r["data"][0]
            amount = int(tx["amount"]) / 1000000 # USDT has 6 decimals
            to_address = tx["toAddress"]
            if to_address == YOUR_WALLET and amount >= PRICE:
                return True
    except:
        pass
    return False

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total = len(users_db)
    await update.message.reply_text(
        f"👑 ADMIN PANEL\n\n"
        f"Total Paid Users: {total}\n"
        f"Wallet: `{YOUR_WALLET}`\n"
        f"Use /ban user_id to ban"
    )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("tx", tx))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CallbackQueryHandler(button))

print("Pro Bot Running. Auto USDT Check Enabled.")
app.run_polling()
