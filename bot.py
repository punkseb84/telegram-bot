import telebot
import os
import requests
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request

# ==============================
# CONFIG
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

tz = ZoneInfo("Europe/Rome")

# ==============================
# STATO BOT
# ==============================
bankroll = 100.0
profit = 0.0
giocate = 0
max_giocate = 2

selected_matches = []
last_chat_id = None

# ==============================
# API
# ==============================
api_requests = 0
MAX_REQUESTS = 7500

def api_call(url):
    global api_requests
    headers = {"x-apisports-key": API_KEY}
    try:
        r = requests.get(url, headers=headers)
        api_requests += 1
        return r.json()
    except:
        return {}

# ==============================
# SEND (CHAT DINAMICA)
# ==============================
def send(msg):
    global last_chat_id
    if last_chat_id:
        bot.send_message(last_chat_id, msg)

# ==============================
# LOGICA xG
# ==============================
def calcola_xg(tiri, porta):
    return (tiri * 0.05) + (porta * 0.15)

# ==============================
# CAMPIONATI
# ==============================
ALL_LEAGUES = [39,140,135,78,61,88,94,144,203,207]

# ==============================
# FILTRO
# ==============================
def filtra_leghe():
    migliori = []
    for league in ALL_LEAGUES:
        url = f"https://v3.football.api-sports.io/fixtures?league={league}&last=10"
        data = api_call(url)

        matches = data.get("response", [])
        if len(matches) < 5:
            continue

        goals = sum((m["goals"]["home"] or 0)+(m["goals"]["away"] or 0) for m in matches)
        media = goals / len(matches)

        if media >= 2.2:
            migliori.append(league)

    return migliori if migliori else ALL_LEAGUES[:3]

# ==============================
# SELEZIONE
# ==============================
def seleziona():
    global selected_matches

    print("🚀 SELEZIONE PARTITE")

    leagues = filtra_leghe()
    today = datetime.now(tz).strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    data = api_call(url)

    matches = []

    for m in data.get("response", []):
        if m["league"]["id"] not in leagues:
            continue

        matches.append({
            "id": m["fixture"]["id"],
            "home": m["teams"]["home"]["name"],
            "away": m["teams"]["away"]["name"]
        })

    selected_matches = matches[:3]

    if not selected_matches:
        send("⚠️ Nessuna partita oggi")
        return

    msg = "📅 PARTITE OGGI\n\n"
    for m in selected_matches:
        msg += f"{m['home']} - {m['away']}\n"

    send(msg)

# ==============================
# LOOP
# ==============================
def loop():
    last = None

    while True:
        now = datetime.now(tz)
        print("⏰ LOOP:", now)

        # FINESTRA 5 MINUTI
        if now.hour == 11 and 30 <= now.minute <= 35 and last != now.date():
            seleziona()
            last = now.date()

        time.sleep(60)

# ==============================
# WEBHOOK (FIX DEFINITIVO)
# ==============================
@app.route('/', methods=['GET'])
def home():
    return "Bot attivo"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    global profit, giocate, bankroll, last_chat_id

    data = request.get_json()
    print("📦 RAW:", data)

    if not data:
        return '', 200

    message = data.get("message") or data.get("edited_message")

    if not message:
        return '', 200

    chat_id = message["chat"]["id"]
    last_chat_id = chat_id  # 🔥 fondamentale

    text = message.get("text", "")
    print("📩 MSG:", text)

    if not text:
        return '', 200

    text = text.lower().strip()

    # ======================
    # COMANDI
    # ======================

    if text.startswith("/start"):
        bot.send_message(chat_id, "🤖 Bot attivo")

    elif text.startswith("/profit"):
        bot.send_message(chat_id, f"💰 Profit: {profit}")

    elif text.startswith("/status"):
        bot.send_message(chat_id, f"Giocate: {giocate} | Bankroll: {bankroll}")

    elif text.startswith("/reset"):
        profit = 0
        giocate = 0
        bankroll = 100
        bot.send_message(chat_id, "Reset fatto")

    elif text.startswith("/api"):
        bot.send_message(chat_id, f"API: {api_requests}/{MAX_REQUESTS}")

    return '', 200

# ==============================
# START
# ==============================
if __name__ == "__main__":

    # reset webhook
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")

    # set webhook
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}/{TELEGRAM_TOKEN}")

    # loop
    threading.Thread(target=loop, daemon=True).start()

    # server
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
