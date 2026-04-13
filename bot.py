import telebot
import os
import time
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_message(msg):
    bot.send_message(CHAT_ID, msg)

def calcola_IA(tiri, in_porta, corner):
    IA = 0
    if tiri >= 10:
        IA += 1
    if in_porta >= 4:
        IA += 1
    if corner >= 5:
        IA += 1
    return IA

def check_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}

    try:
        res = requests.get(url, headers=headers).json()
    except:
        return

    for match in res.get("response", []):
        minuto = match["fixture"]["status"]["elapsed"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        goals_home = match["goals"]["home"]
        goals_away = match["goals"]["away"]

        # 🔥 SOLO 0-0 AL 45'
        if minuto == 45 and goals_home == 0 and goals_away == 0:

            try:
                stats = match["statistics"][0]
                tiri = stats["shots"]["total"] or 0
                in_porta = stats["shots"]["on"] or 0
                corner = stats["corners"] or 0
            except:
                continue

            IA = calcola_IA(tiri, in_porta, corner)

            if IA >= 3:
                segnale = "🟢 ENTRA ORA\nStake: pieno"
            elif IA == 2:
                segnale = "🟡 ENTRA RIDOTTO\nStake: medio"
            else:
                segnale = "🔴 NON ENTRARE"

            msg = f"""⚽ {home} - {away}
⏱ 0-0 HT

📊 Tiri: {tiri}
🎯 In porta: {in_porta}
🚩 Corner: {corner}

{segnale}
"""
            send_message(msg)

# loop continuo
while True:
    check_matches()
    time.sleep(60)
