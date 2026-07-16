import os
import telebot
import gspread
import requests
import time
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from payments import get_payment_message, USDT_WALLET, verify_usdt_tx

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)
user_cooldown = {}

# GOOGLE SHEETS SETUP
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("ThreatVerifyDB").sheet1

def save_bug(user_id, username, title, amount, proof, severity):
    bug_id = len(sheet.get_all_records()) + 1
    sheet.append_row([bug_id, user_id, username, title, amount, proof, severity, "pending", ""])
    return bug_id

def update_bug(bug_id, status, tx_hash=""):
    cell = sheet.find(str(bug_id))
    sheet.update_cell(cell.row, 8, status)
    if tx_hash: sheet.update_cell(cell.row, 9, tx_hash)

def get_bug(bug_id):
    data = sheet.get_all_records()
    return data[int(bug_id)-1]

@bot.message_handler(commands=['start'])
def start(message):
    msg = """👋 *ThreatVerify LIVE v2.1*
*CRYPTO ONLY - USDT TRC20*

*Commands:*
/reportbug Title | Amount | Severity | VideoLink
Ex: /reportbug SQL Injection | 500 | Critical | https://drive.link

/mybugs - Track your bugs
/help - How payments work"""
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['reportbug'])
def report_bug(message):
    # Anti-spam 60s
    if message.from_user.id in user_cooldown and time.time() - user_cooldown[message.from_user.id] < 60:
        bot.reply_to(message, "⏳ Wait 60s before submitting another bug")
        return
    user_cooldown[message.from_user.id] = time.time()

    try:
        _, data = message.text.split(" ", 1)
        title, amount, severity, proof = data.split(" | ")
        bug_id = save_bug(message.from_user.id, message.from_user.username, title, amount, proof, severity)
        bot.reply_to(message, f"✅ Bug #{bug_id} Submitted. Waiting for Admin review.")

        admin_msg = f"""🚨 *NEW BUG #{bug_id}*
*Hunter:* @{message.from_user.username} ID:{message.from_user.id}
*Title:* {title}
*Amount:* {amount} USDT
*Severity:* {severity}
*Proof:* {proof}

Approve: `/approve_{bug_id}`
Reject: `/reject_{bug_id}`"""
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Wrong format. Use: /reportbug Title | Amount | Severity | VideoLink")

@bot.message_handler(commands=['approve'])
def approve(message):
    if message.from_user.id!= ADMIN_ID: return
    bug_id = message.text.split("_")[1]
    bug = get_bug(bug_id)
    msg = get_payment_message(bug['amount'], bug_id)
    bot.send_message(bug['user_id'], msg, parse_mode="Markdown")
    update_bug(bug_id, "payment_sent")
    bot.send_message(ADMIN_ID, f"✅ Payment request sent for Bug #{bug_id}")

@bot.message_handler(commands=['reject'])
def reject(message):
    if message.from_user.id!= ADMIN_ID: return
    bug_id = message.text.split("_")[1]
    bug = get_bug(bug_id)
    bot.send_message(bug['user_id'], f"❌ Bug #{bug_id} was rejected by Admin.")
    update_bug(bug_id, "rejected")
    bot.send_message(ADMIN_ID, f"✅ Bug #{bug_id} Rejected")

@bot.message_handler(commands=['txhash'])
def handle_txhash(message):
    try:
        tx = message.text.replace('/txhash ', '')
        bot.reply_to(message, f"⏳ Verifying TX on TronScan...")
        result = verify_usdt_tx(tx)
        if result:
            bug_id, amount = result
            update_bug(bug_id, "paid", tx)
            bot.reply_to(message, f"✅ *PAYMENT CONFIRMED!*\n{amount} USDT for Bug #{bug_id}\n[View on TronScan](https://tronscan.org/#/transaction/{tx})", parse_mode="Markdown")
            bot.send_message(ADMIN_ID, f"💰 PAID: Bug #{bug_id} {amount} USDT\nTX: {tx}")
        else:
            bot.reply_to(message, "❌ TX invalid. Wrong wallet, amount, or not TRC20")
    except:
        bot.reply_to(message, "Use: /txhash YOUR_TRON_TX_HASH")

@bot.message_handler(commands=['mybugs'])
def my_bugs(message):
    data = sheet.get_all_records()
    my = [b for b in data if str(b['user_id']) == str(message.from_user.id)]
    if not my: bot.reply_to(message, "You have no bugs yet")
    else:
        text = "*Your Bugs:*\n"
        for b in my: text += f"#{b['bug_id']} - {b['title']} - *{b['status']}*\n"
        bot.reply_to(message, text, parse_mode="Markdown")

print("ThreatVerify LIVE Bot v2.1 CRYPTO Running...")
bot.infinity_polling()
