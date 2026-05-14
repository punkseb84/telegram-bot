import telebot
import os
import requests
import threading
import time
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

# =========================================
# CONFIG
# =========================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

tz = ZoneInfo("Europe/Rome")

START_HOUR = 14
END_HOUR = 21

# =========================================
# LEAGUES
# =========================================

LEAGUES = [
    # TOP EUROPA
    39,140,135,78,61,

    # EUROPA OFFENSIVA
    88,94,144,207,
    119,113,179,
    98,292,197,
    253,

    # SECONDE DIVISIONI
    72,73,74,
    79,141,136,
    62,244,

    # SCANDINAVIA
    103,104,105,
    106,107,
    108,109,

    # EST EUROPA
    218,219,220,
    221,222,223,
    224,225,

    # ASIA
    307,308,309,
    310,311,312,

    # SUD AMERICA
    71,128,129,
    130,131,132,
    133,134,

    # USA / CANADA
    253,254,

    # AFRICA / MEDIO ORIENTE
    235,236,237,
    238,239,

    # AUSTRALIA
    188,189,

    # EXTRA OFFENSIVE
    90,91,92,
    95,96,97,
    110,111,112
]

OFFENSIVE_PRIORITY = [
    # TOP OVER LEAGUES
    88,   # Eredivisie
    144,  # Belgio
    119,  # Norvegia
    113,  # Svezia
    179,  # Finlandia
    98,   # Giappone
    292,  # Corea
    39,   # Premier
    78,   # Bundesliga
    94,   # Portogallo
    197,  # Danimarca
    207,  # Svizzera
    253,  # MLS
    188,  # Australia
    90,91,92,
    95,96,97,
    110,111,112
]

# =========================================
# GLOBAL
# =========================================

last_chat_id = None
api_requests = 0

selected_matches = set()
tracked_matches = {}

last_day = None

bankroll = 100.0
bets = []

MAX_OPEN_BETS = 3
MAX_DAILY_LOSS = -10

# =========================================
# DATABASE
# =========================================

conn = sqlite3.connect("trader.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match TEXT,
    league TEXT,
    trigger_type TEXT,
    minute INTEGER,
    odds REAL,
    stake REAL,
    result TEXT,
    profit REAL,
    created_at TEXT
)
''')

conn.commit()

# =========================================
# UTILS
# =========================================

def normalize(text):
    return text.split('@')[0].strip().lower()


def send(msg):
    global last_chat_id

    if last_chat_id:
        try:
            bot.send_message(last_chat_id, msg)
        except:
            pass

# =========================================
# API
# =========================================

def api_call(url):
    global api_requests

    headers = {
        "x-apisports-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        api_requests += 1
        return r.json()

    except Exception as e:
        print("API ERROR", e)
        return {}

# =========================================
# STATS
# =========================================

def get_stat(stats, name):
    for s in stats:
        if s["type"] == name:
            return s["value"] or 0
    return 0

# =========================================
# PREMATCH ENGINE
# =========================================

def score_match(match):

    score = 0

    league_id = match["league"]["id"]

    if league_id in OFFENSIVE_PRIORITY:
        score += 50

    fixture_time = datetime.fromisoformat(
        match["fixture"]["date"].replace("Z", "+00:00")
    ).astimezone(tz)

    if 17 <= fixture_time.hour <= 20:
        score += 20

    return score

# =========================================
# PREMATCH SELECTION
# =========================================

def selezione_pro():

    global selected_matches
    global last_day

    today = datetime.now(tz).date()

    if last_day == today:
        send("⚠️ Partite già selezionate oggi")
        return

    last_day = today

    selected_matches.clear()

    data = api_call(
        f"https://v3.football.api-sports.io/fixtures?date={today}"
    )

    now = datetime.now(tz)

    candidates = []

    for m in data.get("response", []):

        try:

            league_id = m["league"]["id"]

            if league_id not in LEAGUES:
                continue

            fixture_time = datetime.fromisoformat(
                m["fixture"]["date"].replace("Z", "+00:00")
            ).astimezone(tz)

            if fixture_time <= now:
                continue

            if not (START_HOUR <= fixture_time.hour <= END_HOUR):
                continue

            candidates.append(m)

        except:
            continue

    candidates.sort(key=score_match, reverse=True)

    msg = "🔥 PARTITE SELEZIONATE\n\n"

    for m in candidates[:3]:

        match_id = m["fixture"]["id"]

        selected_matches.add(match_id)

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        league = m["league"]["name"]

        kickoff = datetime.fromisoformat(
            m["fixture"]["date"].replace("Z", "+00:00")
        ).astimezone(tz).strftime("%H:%M")

        msg += f"⚽ {home} - {away}\n"
        msg += f"🏆 {league}\n"
        msg += f"🕒 {kickoff}\n\n"

    send(msg)

# =========================================
# LIVE ENGINE
# =========================================

def live_scan():

    data = api_call(
        "https://v3.football.api-sports.io/fixtures?live=all"
    )

    for m in data.get("response", []):

        try:

            match_id = m["fixture"]["id"]

            if match_id not in selected_matches:
                continue

            if tracked_matches.get(match_id, {}).get("finished"):
                continue

            minute = m["fixture"]["status"]["elapsed"]

            g_home = m["goals"]["home"]
            g_away = m["goals"]["away"]

            total = g_home + g_away

            home = m['teams']['home']['name']
            away = m['teams']['away']['name']
            league = m['league']['name']

            name = f"{home} - {away}"

            if match_id not in tracked_matches:
                tracked_matches[match_id] = {}

            state = tracked_matches[match_id]

            # =====================================
            # HT SIGNAL
            # =====================================

            if minute <= 45:

                if total >= 1 and not state.get("ht"):

                    stake = round(bankroll * 0.01, 2)

                    bets.append({
                        "match": name,
                        "type": "HT",
                        "stake": stake,
                        "odds": 1.30,
                        "id": match_id,
                        "resolved": False
                    })

                    send(f"✅ OVER 0.5 HT\n{name}")

                    state["ht"] = True

                continue

            stats = m.get("statistics")

            if not stats:
                continue

            hs = stats[0]["statistics"]
            as_ = stats[1]["statistics"]

            xg = (
                float(get_stat(hs, "Expected Goals (xG)")) +
                float(get_stat(as_, "Expected Goals (xG)"))
            )

            shots = (
                int(get_stat(hs, "Shots on Goal")) +
                int(get_stat(as_, "Shots on Goal"))
            )

            attacks = (
                int(get_stat(hs, "Dangerous Attacks")) +
                int(get_stat(as_, "Dangerous Attacks"))
            )

            corners = (
                int(get_stat(hs, "Corner Kicks")) +
                int(get_stat(as_, "Corner Kicks"))
            )

            momentum = attacks + shots * 2

            quality = xg / shots if shots > 0 else 0

            trigger = False

            # =====================================
            # STANDARD TRIGGER
            # =====================================

            if (
                minute >= 60 and
                total <= 1 and
                xg >= 1.2 and
                momentum >= 70 and
                shots >= 5
            ):
                trigger = True

            # =====================================
            # AGGRESSIVE TRIGGER
            # =====================================

            if (
                68 <= minute <= 75 and
                total <= 1 and
                xg >= 1.6 and
                momentum >= 100 and
                shots >= 10
            ):
                trigger = True

            # =====================================
            # LATE CHAOS
            # =====================================

            if (
                76 <= minute <= 82 and
                total == 1 and
                xg >= 2.0 and
                corners >= 8
            ):
                trigger = True

            # =====================================
            # QUALITY FILTER
            # =====================================

            if quality < 0.08:
                trigger = False

            if shots <= 2:
                trigger = False

            # =====================================
            # SIGNAL
            # =====================================

            if trigger and not state.get("st"):

                if len([
                    b for b in bets
                    if not b["resolved"]
                ]) >= MAX_OPEN_BETS:
                    continue

                stake = round(bankroll * 0.02, 2)

                bets.append({
                    "match": name,
                    "type": "ST",
                    "stake": stake,
                    "odds": 1.80,
                    "id": match_id,
                    "resolved": False
                })

                send(f"⚡ OVER 1.5 ST\n{name}")

                cursor.execute(
                    """
                    INSERT INTO bets (
                        match,
                        league,
                        trigger_type,
                        minute,
                        odds,
                        stake,
                        result,
                        profit,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        name,
                        league,
                        "ST",
                        minute,
                        1.80,
                        stake,
                        "OPEN",
                        0,
                        datetime.now().isoformat()
                    )
                )

                conn.commit()

                state["st"] = True
                state["finished"] = True

        except Exception as e:
            print("LIVE ERROR", e)

# =========================================
# RESULTS
# =========================================

def check_results():

    global bankroll

    data = api_call(
        "https://v3.football.api-sports.io/fixtures?live=all"
    )

    for bet in bets:

        if bet["resolved"]:
            continue

        for m in data.get("response", []):

            if m["fixture"]["id"] != bet["id"]:
                continue

            if m["fixture"]["status"]["short"] == "FT":

                goals = (
                    m["goals"]["home"] +
                    m["goals"]["away"]
                )

                if bet["type"] == "HT":
                    win = goals >= 1
                else:
                    win = goals >= 2

                if win:
                    profit = bet["stake"] * (bet["odds"] - 1)
                    bankroll += profit
                else:
                    profit = -bet["stake"]
                    bankroll += profit

                bet["resolved"] = True

# =========================================
# LOOP
# =========================================

def loop():

    while True:

        try:

            now = datetime.now(tz)

            if now.hour == 11 and 30 <= now.minute <= 35:
                selezione_pro()

            live_scan()
            check_results()

            # polling dinamico
            live_minutes = now.minute

            if live_minutes < 60:
                time.sleep(120)
            elif 60 <= live_minutes <= 75:
                time.sleep(30)
            else:
                time.sleep(15)

        except Exception as e:
            print("LOOP ERROR", e)
            time.sleep(10)

# =========================================
# TELEGRAM COMMANDS
# =========================================

@bot.message_handler(func=lambda m: True)
def handle(msg):

    global last_chat_id
    global bankroll
    global bets

    last_chat_id = msg.chat.id

    text = normalize(msg.text)

    if text == "/start":
        bot.reply_to(msg, "🤖 BOT TRADER PRO ATTIVO")

    elif text == "/bank":
        bot.reply_to(msg, f"💰 Bankroll: {round(bankroll,2)}")

    elif text == "/profit":
        bot.reply_to(msg, f"📈 Profit: {round(bankroll - 100,2)}")

    elif text == "/roi":

        total = sum(
            b["stake"]
            for b in bets
            if b["resolved"]
        )

        roi = (
            ((bankroll - 100) / total) * 100
            if total > 0 else 0
        )

        bot.reply_to(msg, f"📊 ROI: {round(roi,2)}%")

    elif text == "/bets":

        if not bets:
            bot.reply_to(msg, "Nessuna")

        else:
            txt = "\n".join([
                f"{b['match']} - {b['type']}"
                for b in bets
            ])

            bot.reply_to(msg, txt)

    elif text == "/open":

        open_bets = [
            b for b in bets
            if not b["resolved"]
        ]

        if not open_bets:
            bot.reply_to(msg, "Nessuna aperta")

        else:
            txt = "\n".join([
                f"{b['match']} - {b['type']}"
                for b in open_bets
            ])

            bot.reply_to(msg, txt)

    elif text == "/oggi":
        selezione_pro()

    elif text == "/api":
        bot.reply_to(msg, f"📡 API calls: {api_requests}")

# =========================================
# START
# =========================================

print("🚀 BOT TRADER PRO AVVIATO")

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(skip_pending=True)
