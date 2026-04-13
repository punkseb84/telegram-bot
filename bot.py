import telebot
import os
import time
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 📊 STATS
profit = 0
giocate = 0
partite_giocate = {}

LEAGUES_ALLOWED = [39, 140, 135, 78, 61]

def send_message(msg):
    bot.send_message(CHAT_ID, msg)

# 🧠 xG stimato
def calcola_xg(tiri, in_porta):
    return round((tiri * 0.05) + (in_porta * 0.15), 2)

# 🤖 PROBABILITÀ GOL (AI PREDITTIVA)
def probabilita_goal(xg):
    if xg >= 1.5:
        return 80
    elif xg >= 1.2:
        return 70
    elif xg >= 1.0:
        return 60
    elif xg >= 0.8:
        return 50
    else:
        return 30

# 🧠 SCORE AVANZATO
def calcola_score(tiri, in_porta, corner):
    xg = calcola_xg(tiri, in_porta)
    prob = probabilita_goal(xg)

    score = 0

    if prob >= 70:
        score += 3
    elif prob >= 50:
        score += 2
    elif prob >= 40:
        score += 1

    if corner >= 5:
        score += 1

    return score, xg, prob

# 📲 COMANDI TELEGRAM
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🤖 Bot attivo\nComandi: /status /profit /giocate")

@bot.message_handler(commands=['profit'])
def profit_cmd(msg):
    bot.reply_to(msg, f"💰 Profit: {profit}u")

@bot.message_handler(commands=['giocate'])
def giocate_cmd(msg):
    bot.reply_to(msg, f"📊 Giocate: {giocate}")

@bot.message_handler(commands=['status'])
def status_cmd(msg):
    bot.reply_to(msg, f"📊 Stato\nGiocate: {giocate}\nProfit: {profit}u")

@bot.message_handler(commands=['reset'])
def reset_cmd(msg):
    global profit, giocate
    profit = 0
    giocate = 0
    bot.reply_to(msg, "♻️ Reset completato")

# 🔴 LIVE ANALYSIS
def check_matches():
    global giocate

    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}

    try:
        res = requests.get(url, headers=headers).json()
    except:
        return

    for match in res.get("response", []):
        league_id = match["league"]["id"]

        if league_id not in LEAGUES_ALLOWED:
            continue

        fixture_id = match["fixture"]["id"]
        minuto = match["fixture"]["status"]["elapsed"]

        if fixture_id in partite_giocate:
            continue

        if minuto == 45 and match["goals"]["home"] == 0 and match["goals"]["away"] == 0:

            try:
                stats = match["statistics"][0]
                tiri = stats["shots"]["total"] or 0
                in_porta = stats["shots"]["on"] or 0
                corner = stats["corners"] or 0
            except:
                continue

            if tiri < 6:
                continue

            score, xg, prob = calcola_score(tiri, in_porta, corner)

            if prob >= 70:
                stake = 1.5
                segnale = "🟢 FORTE"
            elif prob >= 50:
                stake = 0.7
                segnale = "🟡 MEDIO"
            else:
                continue

            giocate += 1

            partite_giocate[fixture_id] = {
                "stake": stake,
                "home": match["teams"]["home"]["name"],
                "away": match["teams"]["away"]["name"]
            }

            send_message(f"""⚽ {partite_giocate[fixture_id]['home']} - {partite_giocate[fixture_id]['away']}

📊 Tiri: {tiri}
🎯 In porta: {in_porta}
🚩 Corner: {corner}

📈 xG: {xg}
🤖 Probabilità gol: {prob}%

🎯 Segnale: {segnale}
💰 Stake: {stake}u
""")

# 📊 RISULTATI
def check_results():
    global profit

    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}

    try:
        res = requests.get(url, headers=headers).json()
    except:
        return

    for match in res.get("response", []):
        fixture_id = match["fixture"]["id"]

        if fixture_id not in partite_giocate:
            continue

        if match["fixture"]["status"]["elapsed"] >= 90:

            goals = match["goals"]["home"] + match["goals"]["away"]
            stake = partite_giocate[fixture_id]["stake"]

            if goals >= 2:
                profit += stake
                result = "✅ WIN"
            else:
                profit -= stake
                result = "❌ LOSS"

            send_message(f"""📊 RISULTATO
⚽ {partite_giocate[fixture_id]['home']} - {partite_giocate[fixture_id]['away']}

{result}
💰 Profit totale: {profit}u
""")

            del partite_giocate[fixture_id]

# ⏱ LOOP
while True:
    check_matches()
    check_results()
    time.sleep(60)
