# =========================================================
# BOT TRADER PRO FINAL
# VERSIONE COMPLETA SENZA CAMBIO ARCHITETTURA
# =========================================================

import telebot
import os
import requests
import threading
import time
import sqlite3

from datetime import datetime
from zoneinfo import ZoneInfo

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

tz = ZoneInfo("Europe/Rome")

START_HOUR = 14
END_HOUR = 21

MIN_VALUE_ODDS = 1.55
MAX_VALUE_ODDS = 2.40

MAX_OPEN_BETS = 3

BASE_BANKROLL = 100.0

# =========================================================
# LEAGUES
# =========================================================

LEAGUES = [

    # TOP
    39,140,135,78,61,

    # OFFENSIVE
    88,94,144,207,
    119,113,179,
    98,292,197,
    253,

    # SECOND DIVISIONS
    72,73,74,
    79,141,136,

    # EXTRA
    103,104,105,
    218,219,220,
    235,236,237,
    188,189
]

OFFENSIVE_PRIORITY = [
    88,144,119,
    113,179,98,
    292,39,78,
    94,197,207,
    253,188
]

# =========================================================
# GLOBAL
# =========================================================

last_chat_id = None

api_requests = 0

selected_matches = {}
tracked_matches = {}

bets = []

last_day = None

bankroll = BASE_BANKROLL

losing_streak = 0

cache = {}

shot_history = {}

# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect(
    "trader.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_name TEXT,
    league TEXT,
    trigger_type TEXT,
    minute INTEGER,
    odds REAL,
    stake REAL,
    result TEXT,
    profit REAL,
    created_at TEXT
)
""")

conn.commit()

# =========================================================
# UTILS
# =========================================================

def normalize(text):

    return text.split("@")[0].strip().lower()

def send(msg):

    global last_chat_id

    if last_chat_id:

        try:
            bot.send_message(last_chat_id, msg)

        except Exception as e:
            print("SEND ERROR", e)

# =========================================================
# API
# =========================================================

def api_call(url):

    global api_requests

    headers = {
        "x-apisports-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        api_requests += 1

        return r.json()

    except Exception as e:

        print("API ERROR", e)

        return {}

# =========================================================
# CACHE API
# =========================================================

def cached_api_call(url, ttl=60):

    now = time.time()

    if url in cache:

        ts, data = cache[url]

        if now - ts < ttl:
            return data

    data = api_call(url)

    cache[url] = (now, data)

    return data

# =========================================================
# STATS
# =========================================================

def get_stat(stats, name):

    for s in stats:

        if s["type"] == name:
            return s["value"] or 0

    return 0

# =========================================================
# VALUE ODDS
# =========================================================

def get_live_odds(fixture_id):

    data = cached_api_call(
        f"https://v3.football.api-sports.io/odds/live?fixture={fixture_id}",
        ttl=30
    )

    try:

        bookmakers = data["response"][0]["bookmakers"]

        for bookmaker in bookmakers:

            for bet in bookmaker["bets"]:

                if bet["name"] == "Over/Under":

                    for value in bet["values"]:

                        if value["value"] == "Over 1.5":
                            return float(value["odd"])

    except:
        return None

    return None

# =========================================================
# SCORE MATCH
# =========================================================

def score_match(match):

    score = 0

    league_id = match["league"]["id"]

    if league_id in OFFENSIVE_PRIORITY:
        score += 50

    fixture_time = datetime.fromisoformat(
        match["fixture"]["date"].replace("Z","+00:00")
    ).astimezone(tz)

    if 17 <= fixture_time.hour <= 20:
        score += 20

    return score

# =========================================================
# PREMATCH
# =========================================================

def selezione_pro():

    global last_day
    global selected_matches

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
                m["fixture"]["date"].replace("Z","+00:00")
            ).astimezone(tz)

            if fixture_time <= now:
                continue

            if not (
                START_HOUR <= fixture_time.hour <= END_HOUR
            ):
                continue

            candidates.append(m)

        except:
            continue

    candidates.sort(
        key=score_match,
        reverse=True
    )

    msg = "🔥 PARTITE SELEZIONATE\n\n"

    for m in candidates[:3]:

        match_id = m["fixture"]["id"]

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        league = m["league"]["name"]

        kickoff = datetime.fromisoformat(
            m["fixture"]["date"].replace("Z","+00:00")
        ).astimezone(tz).strftime("%H:%M")

        selected_matches[match_id] = {
            "home": home,
            "away": away,
            "league": league,
            "kickoff": kickoff
        }

        msg += (
            f"⚽ {home} - {away}\n"
            f"🏆 {league}\n"
            f"🕒 {kickoff}\n\n"
        )

    send(msg)

# =========================================================
# OPEN BETS LEAGUE
# =========================================================

def league_open_bets(league):

    return len([

        b for b in bets

        if (
            not b["resolved"]
            and b["league"] == league
        )
    ])

# =========================================================
# LIVE ENGINE
# =========================================================

def live_scan():

    global bankroll
    global losing_streak

    data = cached_api_call(
        "https://v3.football.api-sports.io/fixtures?live=all",
        ttl=15
    )

    for m in data.get("response", []):

        try:

            match_id = m["fixture"]["id"]

            if match_id not in selected_matches:
                continue

            state = tracked_matches.setdefault(
                match_id,
                {}
            )

            if state.get("finished"):
                continue

            minute = m["fixture"]["status"]["elapsed"]

            home_goals = m["goals"]["home"]
            away_goals = m["goals"]["away"]

            total_goals = home_goals + away_goals

            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]

            league = m["league"]["name"]

            match_name = f"{home} - {away}"

            # =================================================
            # HT SIGNAL
            # =================================================

            if minute <= 45:

                if (
                    total_goals >= 1
                    and not state.get("ht")
                ):

                    stake = round(
                        bankroll * 0.01,
                        2
                    )

                    bets.append({

                        "match": match_name,
                        "league": league,
                        "type": "HT",
                        "stake": stake,
                        "odds": 1.30,
                        "id": match_id,
                        "resolved": False,
                        "profit": 0
                    })

                    send(
                        f"✅ OVER 0.5 HT\n\n"
                        f"{match_name}"
                    )

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

            red_home = int(
                get_stat(hs, "Red Cards")
            )

            red_away = int(
                get_stat(as_, "Red Cards")
            )

            momentum = attacks + shots * 2

            # =================================================
            # RED CARD BOOST
            # =================================================

            if red_home + red_away >= 1:
                momentum += 20

            # =================================================
            # POST GOAL CHAOS
            # =================================================

            if total_goals == 1 and minute >= 70:
                momentum += 15

            quality = (
                xg / shots
                if shots > 0
                else 0
            )

            # =================================================
            # SHOT ACCELERATION
            # =================================================

            shot_history.setdefault(
                match_id,
                []
            )

            shot_history[match_id].append(
                (minute, shots)
            )

            recent = [

                s for m_, s in shot_history[match_id]

                if minute - m_ <= 10
            ]

            acceleration = 0

            if len(recent) >= 2:
                acceleration = recent[-1] - recent[0]

            # =================================================
            # VALUE ODDS
            # =================================================

            odds = get_live_odds(match_id)

            if not odds:
                continue

            trigger = False

            # =================================================
            # STANDARD
            # =================================================

            if (
                minute >= 60
                and total_goals <= 1
                and xg >= 1.2
                and momentum >= 70
                and shots >= 5
            ):
                trigger = True

            # =================================================
            # AGGRESSIVE
            # =================================================

            if (
                68 <= minute <= 75
                and total_goals <= 1
                and xg >= 1.6
                and momentum >= 100
                and shots >= 10
            ):
                trigger = True

            # =================================================
            # LATE CHAOS
            # =================================================

            if (
                76 <= minute <= 82
                and total_goals == 1
                and xg >= 2
                and corners >= 8
            ):
                trigger = True

            # =================================================
            # SHOT ACCELERATION
            # =================================================

            if acceleration >= 4:
                trigger = True

            # =================================================
            # QUALITY FILTERS
            # =================================================

            if quality < 0.08:
                trigger = False

            if shots <= 2:
                trigger = False

            if odds < MIN_VALUE_ODDS:
                trigger = False

            if odds > MAX_VALUE_ODDS:
                trigger = False

            # =================================================
            # MAX OPEN BETS
            # =================================================

            open_bets = len([

                b for b in bets

                if not b["resolved"]
            ])

            if open_bets >= MAX_OPEN_BETS:
                trigger = False

            # =================================================
            # MAX LEAGUE EXPOSURE
            # =================================================

            if league_open_bets(league) >= 1:
                trigger = False

            # =================================================
            # SIGNAL
            # =================================================

            if trigger and not state.get("st"):

                risk_multiplier = 1

                if losing_streak >= 3:
                    risk_multiplier = 0.5

                stake = round(
                    bankroll * 0.02 * risk_multiplier,
                    2
                )

                bets.append({

                    "match": match_name,
                    "league": league,
                    "type": "ST",
                    "stake": stake,
                    "odds": odds,
                    "id": match_id,
                    "resolved": False,
                    "profit": 0
                })

                send(
                    f"⚡ OVER 1.5 ST\n\n"
                    f"{match_name}\n"
                    f"🕒 {minute}'\n"
                    f"📈 xG: {round(xg,2)}\n"
                    f"🎯 Shots: {shots}\n"
                    f"⚡ Momentum: {momentum}\n"
                    f"💰 Odds: {odds}"
                )

                cursor.execute("""

                INSERT INTO bets (
                    match_name,
                    league,
                    trigger_type,
                    minute,
                    odds,
                    stake,
                    result,
                    profit,
                    created_at
                )

                VALUES (?,?,?,?,?,?,?,?,?)

                """, (

                    match_name,
                    league,
                    "ST",
                    minute,
                    odds,
                    stake,
                    "OPEN",
                    0,
                    datetime.now().isoformat()
                ))

                conn.commit()

                state["st"] = True

        except Exception as e:

            print("LIVE ERROR", e)

# =========================================================
# CHECK RESULTS
# =========================================================

def check_results():

    global bankroll
    global losing_streak

    data = cached_api_call(
        "https://v3.football.api-sports.io/fixtures?live=all",
        ttl=30
    )

    for bet in bets:

        if bet["resolved"]:
            continue

        for m in data.get("response", []):

            if m["fixture"]["id"] != bet["id"]:
                continue

            if m["fixture"]["status"]["short"] != "FT":
                continue

            goals = (
                m["goals"]["home"] +
                m["goals"]["away"]
            )

            if bet["type"] == "HT":
                win = goals >= 1
            else:
                win = goals >= 2

            if win:

                profit = round(
                    bet["stake"] * (
                        bet["odds"] - 1
                    ),
                    2
                )

                bankroll += profit

                losing_streak = 0

                result = "WIN"

            else:

                profit = -bet["stake"]

                bankroll += profit

                losing_streak += 1

                result = "LOSS"

            bet["profit"] = profit

            bet["resolved"] = True

            cursor.execute("""

            UPDATE bets

            SET result=?,
                profit=?

            WHERE match_name=? AND result='OPEN'

            """, (

                result,
                profit,
                bet["match"]
            ))

            conn.commit()

# =========================================================
# LOOP
# =========================================================

def loop():

    while True:

        try:

            now = datetime.now(tz)

            # =============================================
            # AUTO PREMATCH
            # =============================================

            if (
                now.hour == 11
                and 30 <= now.minute <= 35
            ):
                selezione_pro()

            live_scan()

            check_results()

            # =============================================
            # DYNAMIC POLLING
            # =============================================

            if now.hour < 18:
                time.sleep(60)

            elif 18 <= now.hour <= 22:
                time.sleep(30)

            else:
                time.sleep(120)

        except Exception as e:

            print("LOOP ERROR", e)

            time.sleep(10)

# =========================================================
# TELEGRAM
# =========================================================

@bot.message_handler(func=lambda m: True)
def handle(msg):

    global last_chat_id
    global bankroll
    global bets

    last_chat_id = msg.chat.id

    text = normalize(msg.text)

    # =====================================================
    # START
    # =====================================================

    if text == "/start":

        bot.reply_to(
            msg,
            "🤖 BOT TRADER PRO ATTIVO"
        )

    # =====================================================
    # TODAY
    # =====================================================

    elif text == "/today":

        if not selected_matches:

            bot.reply_to(
                msg,
                "Nessuna partita attiva"
            )

        else:

            txt = "📅 PARTITE ATTIVE\n\n"

            for _, v in selected_matches.items():

                txt += (
                    f"{v['home']} - {v['away']}\n"
                    f"{v['league']}\n"
                    f"{v['kickoff']}\n\n"
                )

            bot.reply_to(msg, txt)

    # =====================================================
    # OGGI
    # =====================================================

    elif text == "/oggi":

        selezione_pro()

    # =====================================================
    # BANK
    # =====================================================

    elif text == "/bank":

        bot.reply_to(
            msg,
            f"💰 Bankroll: {round(bankroll,2)}"
        )

    # =====================================================
    # PROFIT
    # =====================================================

    elif text == "/profit":

        bot.reply_to(
            msg,
            f"📈 Profit: {round(bankroll - BASE_BANKROLL,2)}"
        )

    # =====================================================
    # ROI
    # =====================================================

    elif text == "/roi":

        total_stake = sum([

            b["stake"]

            for b in bets

            if b["resolved"]
        ])

        roi = 0

        if total_stake > 0:

            roi = (
                (bankroll - BASE_BANKROLL)
                / total_stake
            ) * 100

        bot.reply_to(
            msg,
            f"📊 ROI: {round(roi,2)}%"
        )

    # =====================================================
    # BETS
    # =====================================================

    elif text == "/bets":

        if not bets:

            bot.reply_to(
                msg,
                "Nessuna giocata"
            )

        else:

            txt = "📚 BETS\n\n"

            for b in bets[-20:]:

                txt += (
                    f"{b['match']} | "
                    f"{b['type']} | "
                    f"{b['odds']}\n"
                )

            bot.reply_to(msg, txt)

    # =====================================================
    # OPEN
    # =====================================================

    elif text == "/open":

        open_bets = [

            b for b in bets

            if not b["resolved"]
        ]

        if not open_bets:

            bot.reply_to(
                msg,
                "Nessuna aperta"
            )

        else:

            txt = "🔓 OPEN BETS\n\n"

            for b in open_bets:

                txt += (
                    f"{b['match']} | "
                    f"{b['type']}\n"
                )

            bot.reply_to(msg, txt)

    # =====================================================
    # API
    # =====================================================

    elif text == "/api":

        bot.reply_to(
            msg,
            f"📡 API Calls: {api_requests}"
        )

    # =====================================================
    # STATS
    # =====================================================

    elif text == "/stats":

        total = len([

            b for b in bets

            if b["resolved"]
        ])

        wins = len([

            b for b in bets

            if (
                b["resolved"]
                and b["profit"] > 0
            )
        ])

        losses = total - wins

        total_stake = sum([

            b["stake"]

            for b in bets

            if b["resolved"]
        ])

        roi = 0

        if total_stake > 0:

            roi = (
                (bankroll - BASE_BANKROLL)
                / total_stake
            ) * 100

        winrate = 0

        if total > 0:
            winrate = (wins / total) * 100

        txt = (

            "📊 STATS\n\n"

            f"Bets: {total}\n"
            f"Wins: {wins}\n"
            f"Losses: {losses}\n"
            f"ROI: {round(roi,2)}%\n"
            f"Winrate: {round(winrate,2)}%\n"
            f"Losing streak: {losing_streak}"
        )

        bot.reply_to(msg, txt)

    # =====================================================
    # LEAGUES
    # =====================================================

    elif text == "/leagues":

        data = {}

        for b in bets:

            if not b["resolved"]:
                continue

            lg = b["league"]

            if lg not in data:
                data[lg] = 0

            data[lg] += b["profit"]

        txt = "🏆 LEAGUES\n\n"

        for lg, profit in sorted(
            data.items(),
            key=lambda x: x[1],
            reverse=True
        ):

            txt += f"{lg}: {round(profit,2)}\n"

        bot.reply_to(msg, txt)

    # =====================================================
    # HISTORY
    # =====================================================

    elif text == "/history":

        rows = cursor.execute("""

        SELECT match_name,
               trigger_type,
               profit

        FROM bets

        ORDER BY id DESC

        LIMIT 10

        """).fetchall()

        if not rows:

            bot.reply_to(
                msg,
                "Storico vuoto"
            )

        else:

            txt = "📚 HISTORY\n\n"

            for r in rows:

                txt += (
                    f"{r[0]} | "
                    f"{r[1]} | "
                    f"{r[2]}\n"
                )

            bot.reply_to(msg, txt)

    # =====================================================
    # PERFORMANCE
    # =====================================================

    elif text == "/performance":

        open_bets = len([

            b for b in bets

            if not b["resolved"]
        ])

        txt = (

            "📈 PERFORMANCE\n\n"

            f"Bankroll: {round(bankroll,2)}\n"
            f"Profit: {round(bankroll - BASE_BANKROLL,2)}\n"
            f"API Calls: {api_requests}\n"
            f"Open Bets: {open_bets}"
        )

        bot.reply_to(msg, txt)

# =========================================================
# START
# =========================================================

print("🚀 BOT TRADER PRO FINAL AVVIATO")

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(skip_pending=True)
