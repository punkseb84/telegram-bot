import telebot
import os
import requests
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# ==============================
# CONFIG
# ==============================
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")

print("DEBUG API_KEY:", API_KEY)

bot = telebot.TeleBot(TOKEN)
tz = ZoneInfo("Europe/Rome")

# ==============================
# COMPETIZIONI EUROPEE
# ==============================
LEAGUES = [
    39, 140, 135, 78, 61,
    94, 88, 203, 144, 207,
    119, 71, 62, 79, 141,
    136, 103, 98,
    2, 3, 848
]

# ==============================
# STATO
# ==============================
last_chat_id = None
loop_started = False
api_requests = 0

# ==============================
# CACHE
# ==============================
cache = {}
team_cache = {}
tracked_matches = {}

CACHE_TIME = 300
MAX_REQUESTS = 7000

# ==============================
# API CALL
# ==============================
def api_call(url):
    global api_requests

    now = time.time()

    if url in cache:
        data, timestamp = cache[url]
        if now - timestamp < CACHE_TIME:
            return data

    headers = {
        "x-apisports-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        api_requests += 1

        if r.status_code != 200:
            print("API ERROR:", r.status_code)
            return {}

        data = r.json()
        cache[url] = (data, now)

        return data

    except:
        return {}

# ==============================
# SEND
# ==============================
def send(msg):
    if last_chat_id:
        bot.send_message(last_chat_id, msg)

# ==============================
# STAT SAFE
# ==============================
def get_stat(stats, name):
    for s in stats:
        if s["type"] == name:
            return s["value"] or 0
    return 0

# ==============================
# LIVE SCAN (STRATEGIA)
# ==============================
def live_scan():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    data = api_call(url)

    for m in data.get("response", []):
        try:
            league_id = m["league"]["id"]

            # filtro Europa
            if league_id not in LEAGUES:
                continue

            match_id = m["fixture"]["id"]

            # skip se già finita
            if tracked_matches.get(match_id, {}).get("finished"):
                continue

            minute = m["fixture"]["status"]["elapsed"]
            goals_home = m["goals"]["home"]
            goals_away = m["goals"]["away"]
            total_goals = goals_home + goals_away

            match_name = f"{m['teams']['home']['name']} - {m['teams']['away']['name']}"

            # init tracking
            if match_id not in tracked_matches:
                tracked_matches[match_id] = {
                    "finished": False,
                    "first_goal_sent": False,
                    "second_half_alert": False
                }

            stats = m.get("statistics")
            if not stats:
                continue

            home_stats = stats[0]["statistics"]
            away_stats = stats[1]["statistics"]

            xg = float(get_stat(home_stats, "Expected Goals (xG)")) + \
                 float(get_stat(away_stats, "Expected Goals (xG)"))

            momentum = int(get_stat(home_stats, "Dangerous Attacks")) + \
                       int(get_stat(away_stats, "Dangerous Attacks"))

            shots = int(get_stat(home_stats, "Shots on Goal")) + \
                    int(get_stat(away_stats, "Shots on Goal"))

            # ==============================
            # PRIMO TEMPO → GOL
            # ==============================
            if minute <= 45 and total_goals >= 1:
                if not tracked_matches[match_id]["first_goal_sent"]:
                    send(f"""✅ OVER 0.5 HT IN CASSA

{match_name}
Minuto: {minute}
""")
                    tracked_matches[match_id]["finished"] = True
                    continue

            # ==============================
            # SECONDO TEMPO → MINUTO 60
            # ==============================
            if minute >= 60 and total_goals == 0:
                if not tracked_matches[match_id]["second_half_alert"]:

                    if xg >= 1.2 and momentum >= 70 and shots >= 5:
                        send(f"""⚡ OVER 1.5 SECONDO TEMPO

{match_name}

Minuto: {minute}
xG: {xg}
Momentum: {momentum}
Tiri: {shots}
""")
                    else:
                        print(f"❌ PARTITA SCARTATA: {match_name}")

                    tracked_matches[match_id]["finished"] = True
                    continue

        except Exception as e:
            print("LIVE ERROR:", e)

# ==============================
# LOOP
# ==============================
def loop():
    while True:
        now = datetime.now(tz)

        if 12 <= now.hour <= 23:
            live_scan()

        time.sleep(180)

# ==============================
# TELEGRAM
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global last_chat_id, loop_started

    last_chat_id = msg.chat.id
    text = msg.text.lower() if msg.text else ""

    if text.startswith("/start"):
        bot.reply_to(msg, "🤖 BOT LIVE STRATEGY ATTIVO")

        if not loop_started:
            threading.Thread(target=loop, daemon=True).start()
            loop_started = True

    elif text.startswith("/live"):
        live_scan()
        bot.reply_to(msg, "🔄 Scan live eseguito")

    elif text.startswith("/api"):
        bot.reply_to(msg, f"API calls: {api_requests}")

# ==============================
# START
# ==============================
print("🚀 BOT LIVE DEFINITIVO ATTIVO")

bot.infinity_polling(skip_pending=True, none_stop=True)
