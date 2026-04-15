import telebot
import os
import requests
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request

# 🔑 CONFIG
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
API_KEY = os.getenv("API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

tz = ZoneInfo("Europe/Rome")

# ==============================
# 📲 MENU COMANDI
# ==============================
bot.set_my_commands([
    telebot.types.BotCommand("start", "Avvia bot"),
    telebot.types.BotCommand("status", "Stato bot"),
    telebot.types.BotCommand("api", "Uso API")
])

# ==============================
# 📩 SEND
# ==============================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg)
    except Exception as e:
        print("Errore invio:", e)

# ==============================
# 📡 API TRACKING
# ==============================
api_requests = 0
MAX_REQUESTS = 7500

def api_call(url):
    global api_requests

    headers = {"x-apisports-key": API_KEY}

    try:
        response = requests.get(url, headers=headers)
        api_requests += 1
        return response.json()
    except:
        return {}

# ==============================
# 📲 COMANDI
# ==============================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🤖 Bot attivo (webhook)")

@bot.message_handler(commands=['status'])
def status(msg):
    bot.reply_to(msg, "✅ Bot online")

@bot.message_handler(commands=['api'])
def api_status(msg):
    percent = round((api_requests / MAX_REQUESTS) * 100, 1)

    bot.reply_to(msg, f"""📡 API USAGE
Richieste: {api_requests}/{MAX_REQUESTS}
Utilizzo: {percent}%""")

# ==============================
# 🌐 WEBHOOK ROUTES
# ==============================
@app.route('/', methods=['GET'])
def home():
    return "Bot attivo"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# ==============================
# 🔁 LOOP (opzionale)
# ==============================
def loop_live():
    while True:
        print("🔄 Bot attivo...")
        time.sleep(60)

# ==============================
# ▶️ AVVIO
# ==============================
if __name__ == "__main__":

    # 🔥 RESET webhook
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")

    # 🔥 SET webhook
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}/{TELEGRAM_TOKEN}")

    print("✅ Webhook attivo")

    threading.Thread(target=loop_live).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
