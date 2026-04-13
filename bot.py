import telebot
import os
import time
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

profit = 0
giocate = 0
matches_state = {}

LEAGUES_ALLOWED = [39, 140, 135, 78, 61]

def send(msg):
    bot.send_message(CHAT_ID, msg)

# 🧠 xG
def calcola_xg(tiri, in_porta):
    return (tiri * 0.05) + (in_porta * 0.15)

# 🤖 probabilità
def prob_goal(xg):
    if xg >= 1.5: return 80
    if xg >= 1.2: return 70
    if xg >= 1.0: return 60
    if xg >= 0.8: return 50
    return 30

# 📲 COMANDI
@bot.message_handler(commands=['profit'])
def cmd_profit(msg):
    bot.reply_to(msg, f"💰 Profit: {profit}u")

@bot.message_handler(commands=['status'])
def cmd_status(msg):
    bot.reply_to(msg, f"📊 Giocate: {giocate}\n💰 Profit: {profit}u")

# 🔴 LIVE
def check_matches():
    global giocate, profit

    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}

    try:
        data = requests.get(url, headers=headers).json()
    except:
        return

    for m in data.get("response", []):
        league = m["league"]["id"]
        if league not in LEAGUES_ALLOWED:
            continue

        fid = m["fixture"]["id"]
        minute = m["fixture"]["status"]["elapsed"]

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        goals = (m["goals"]["home"] or 0) + (m["goals"]["away"] or 0)

        try:
            stats = m["statistics"][0]
            tiri = stats["shots"]["total"] or 0
            in_porta = stats["shots"]["on"] or 0
            corner = stats["corners"] or 0
        except:
            continue

        xg = round(calcola_xg(tiri, in_porta), 2)
        prob = prob_goal(xg)

        if fid not in matches_state:
            matches_state[fid] = {
                "sent": False,
                "entered": False,
                "last_xg": xg,
                "home": home,
                "away": away,
                "stake": 0
            }

        state = matches_state[fid]

        # 🚫 partita morta
        if minute == 45 and goals == 0 and tiri < 6:
            send(f"❌ {home}-{away}\nPartita lenta → NO BET")
            state["sent"] = True
            continue

        # 🔥 ENTRY TIMING (50-60)
        if 50 <= minute <= 60 and not state["entered"]:

            if prob >= 70:
                stake = 1.5
                segnale = "🟢 ENTRA ORA"
            elif prob >= 50:
                stake = 0.7
                segnale = "🟡 ENTRA RIDOTTO"
            else:
                continue

            giocate += 1
            state["entered"] = True
            state["stake"] = stake

            send(f"""⚽ {home}-{away}

⏱ {minute}'
📈 xG: {xg}
🤖 Prob: {prob}%

🔥 {segnale}
💰 Stake: {stake}u
""")

        # 🔄 UPDATE DINAMICO
        if state["entered"] and xg > state["last_xg"] + 0.3:
            send(f"""📈 UPDATE

{home}-{away}
xG in crescita: {state['last_xg']} → {xg}

🔥 partita si accende
""")
            state["last_xg"] = xg

        # ⚠️ rischio
        if state["entered"] and minute > 70 and xg < 0.8:
            send(f"""⚠️ ATTENZIONE

{home}-{away}
ritmo basso → rischio alto
""")

        # ⚽ GOL
        if state["entered"] and goals >= 1:
            send(f"""⚽ GOL!

{home}-{away}

👉 valuta cashout o lascia correre
""")
            state["entered"] = False

        # 📊 RISULTATO
        if minute >= 90 and state["stake"] > 0:

            if goals >= 2:
                profit += state["stake"]
                result = "✅ WIN"
            else:
                profit -= state["stake"]
                result = "❌ LOSS"

            send(f"""📊 RISULTATO

{home}-{away}
{result}

💰 Profit: {profit}u
""")

            del matches_state[fid]

while True:
    check_matches()
    time.sleep(60)
