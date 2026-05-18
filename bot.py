# =========================================================
# BOT TRADER PRO ELITE ULTRA
# VERSIONE DATA-ADAPTIVE REALISTICA
# =========================================================

import telebot
from telebot import types

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

DEBUG_MODE = True

LIVE_INTERVAL = 30

START_HOUR = 14
END_HOUR = 21

# =========================================================
# LEAGUES
# =========================================================

LEAGUES = [

    39,140,135,78,61,
    88,94,144,207,
    119,113,179,
    98,292,197,
    253,188,

    72,73,74,
    79,141,136,
    62,244,

    103,104,105,
    106,107,108,
    109,110,111,
    112,114,115,

    218,219,220,
    221,222,223,

    235,236,237,
    238,239,240
]

OFFENSIVE_PRIORITY = [

    88,
    144,
    119,
    113,
    179,
    98,
    292,
    39,
    78,
    94,
    197,
    207,
    253,
    188,
    235
]

# =========================================================
# GLOBAL
# =========================================================

last_chat_id = None

api_requests = 0

selected_matches = {}

triggered_matches = {}

stats_cache = {}

last_day = None

# =========================================================
# DB
# =========================================================

conn = sqlite3.connect(
    "trader.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""

CREATE TABLE IF NOT EXISTS selections (

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_name TEXT,
    score REAL,
    created_at TEXT

)

""")

conn.commit()

# =========================================================
# TELEGRAM COMMANDS
# =========================================================

bot.set_my_commands([

    types.BotCommand(
        "start",
        "Avvia il bot"
    ),

    types.BotCommand(
        "oggi",
        "Seleziona partite"
    ),

    types.BotCommand(
        "today",
        "Partite attive"
    ),

    types.BotCommand(
        "api",
        "API usage"
    ),

    types.BotCommand(
        "debug",
        "Debug status"
    )

])

# =========================================================
# UTILS
# =========================================================

def log(*args):

    if DEBUG_MODE:
        print("[DEBUG]", *args)

def send(msg):

    global last_chat_id

    if last_chat_id:

        try:

            bot.send_message(
                last_chat_id,
                msg
            )

        except Exception as e:

            print(e)

def normalize(text):

    return text.split("@")[0].strip().lower()

# =========================================================
# API
# =========================================================

def api_call(url):

    global api_requests

    headers = {

        "x-apisports-key": API_KEY,
        "x-rapidapi-host":
        "v3.football.api-sports.io"

    }

    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        api_requests += 1

        return r.json()

    except Exception as e:

        log("API ERROR", e)

        return {}

# =========================================================
# STATS CACHE
# =========================================================

def get_fixture_statistics(fixture_id):

    now = time.time()

    if fixture_id in stats_cache:

        ts, data = stats_cache[fixture_id]

        if now - ts < 20:
            return data

    url = (

        f"https://v3.football.api-sports.io/"
        f"fixtures/statistics?"
        f"fixture={fixture_id}"

    )

    data = api_call(url)

    stats_cache[fixture_id] = (
        now,
        data
    )

    return data

# =========================================================
# TEAM STATS
# =========================================================

def get_team_stats(team_id, league_id):

    url = (

        f"https://v3.football.api-sports.io/"
        f"teams/statistics?"
        f"league={league_id}&"
        f"season=2026&"
        f"team={team_id}"

    )

    return api_call(url)

# =========================================================
# ANALYZE TEAM
# =========================================================

def analyze_team(data):

    try:

        played = (
            data["response"]
            ["fixtures"]["played"]["total"]
        )

        gf = (
            data["response"]
            ["goals"]["for"]["total"]["total"]
        )

        ga = (
            data["response"]
            ["goals"]["against"]["total"]["total"]
        )

        return (gf + ga) / played

    except:
        return 2

# =========================================================
# SCORE MATCH
# =========================================================

def score_match(match):

    try:

        score = 0

        league_id = (
            match["league"]["id"]
        )

        home_id = (
            match["teams"]["home"]["id"]
        )

        away_id = (
            match["teams"]["away"]["id"]
        )

        # =========================================
        # OFFENSIVE LEAGUE
        # =========================================

        if league_id in OFFENSIVE_PRIORITY:
            score += 50

        # =========================================
        # KICKOFF BONUS
        # =========================================

        kickoff = datetime.fromisoformat(

            match["fixture"]["date"].replace(
                "Z",
                "+00:00"
            )

        ).astimezone(tz)

        if 17 <= kickoff.hour <= 20:
            score += 20

        # =========================================
        # TEAM STATS
        # =========================================

        home_stats = analyze_team(
            get_team_stats(
                home_id,
                league_id
            )
        )

        away_stats = analyze_team(
            get_team_stats(
                away_id,
                league_id
            )
        )

        score += (
            home_stats +
            away_stats
        ) * 10

        return round(score, 2)

    except Exception as e:

        log("SCORE ERROR", e)

        return 0

# =========================================================
# PREMATCH ENGINE
# =========================================================

def selezione_pro():

    global selected_matches
    global last_day

    today = datetime.now(tz).date()

    if last_day == today:

        send(
            "⚠️ Selezione già effettuata oggi"
        )

        return

    last_day = today

    selected_matches.clear()

    data = api_call(

        f"https://v3.football.api-sports.io/"
        f"fixtures?date={today}"

    )

    now = datetime.now(tz)

    scored = []

    for m in data.get("response", []):

        try:

            league_id = (
                m["league"]["id"]
            )

            if league_id not in LEAGUES:
                continue

            kickoff = datetime.fromisoformat(

                m["fixture"]["date"].replace(
                    "Z",
                    "+00:00"
                )

            ).astimezone(tz)

            if kickoff <= now:
                continue

            if not (
                START_HOUR <= kickoff.hour <= END_HOUR
            ):
                continue

            score = score_match(m)

            scored.append(
                (score, m)
            )

        except:
            continue

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    top = scored[:3]

    msg = (
        "🔥 PARTITE SELEZIONATE\n\n"
    )

    for score, m in top:

        fixture_id = (
            m["fixture"]["id"]
        )

        home = (
            m["teams"]["home"]["name"]
        )

        away = (
            m["teams"]["away"]["name"]
        )

        league = (
            m["league"]["name"]
        )

        kickoff = datetime.fromisoformat(

            m["fixture"]["date"].replace(
                "Z",
                "+00:00"
            )

        ).astimezone(tz).strftime("%H:%M")

        selected_matches[fixture_id] = {

            "home": home,
            "away": away,
            "league": league,
            "kickoff": kickoff,
            "score": score

        }

        msg += (

            f"⚽ {home} - {away}\n"
            f"🏆 {league}\n"
            f"🕒 {kickoff}\n"
            f"📈 Score {score}\n\n"

        )

    send(msg)

# =========================================================
# GET STAT
# =========================================================

def get_stat(stats, name):

    for s in stats:

        if s["type"] == name:
            return s["value"]

    return None

# =========================================================
# SAFE INT
# =========================================================

def safe_int(v):

    try:

        if v is None:
            return 0

        if isinstance(v, str):

            v = v.replace("%", "")

        return int(float(v))

    except:
        return 0

# =========================================================
# LIVE ENGINE
# =========================================================

def live_scan():

    live = api_call(

        "https://v3.football.api-sports.io/"
        "fixtures?live=all"

    )

    matches = live.get("response", [])

    log("LIVE FOUND", len(matches))

    for m in matches:

        try:

            fixture_id = (
                m["fixture"]["id"]
            )

            if fixture_id not in selected_matches:
                continue

            home = (
                m["teams"]["home"]["name"]
            )

            away = (
                m["teams"]["away"]["name"]
            )

            match_name = (
                f"{home} - {away}"
            )

            minute = (
                m["fixture"]["status"]
                ["elapsed"]
            )

            if not minute:
                continue

            home_goals = (
                m["goals"]["home"] or 0
            )

            away_goals = (
                m["goals"]["away"] or 0
            )

            total_goals = (
                home_goals + away_goals
            )

            # =====================================
            # STATISTICS API
            # =====================================

            stats_data = get_fixture_statistics(
                fixture_id
            )

            stats_response = (
                stats_data.get("response", [])
            )

            if len(stats_response) < 2:

                log(
                    "NO STATS",
                    match_name
                )

                continue

            hs = stats_response[0]["statistics"]
            as_ = stats_response[1]["statistics"]

            # =====================================
            # REAL PARAMETERS
            # =====================================

            shots_on_goal = (

                safe_int(
                    get_stat(
                        hs,
                        "Shots on Goal"
                    )
                )

                +

                safe_int(
                    get_stat(
                        as_,
                        "Shots on Goal"
                    )
                )

            )

            total_shots = (

                safe_int(
                    get_stat(
                        hs,
                        "Total Shots"
                    )
                )

                +

                safe_int(
                    get_stat(
                        as_,
                        "Total Shots"
                    )
                )

            )

            corners = (

                safe_int(
                    get_stat(
                        hs,
                        "Corner Kicks"
                    )
                )

                +

                safe_int(
                    get_stat(
                        as_,
                        "Corner Kicks"
                    )
                )

            )

            possession_home = safe_int(

                get_stat(
                    hs,
                    "Ball Possession"
                )

            )

            possession_away = safe_int(

                get_stat(
                    as_,
                    "Ball Possession"
                )

            )

            passes = (

                safe_int(
                    get_stat(
                        hs,
                        "Total passes"
                    )
                )

                +

                safe_int(
                    get_stat(
                        as_,
                        "Total passes"
                    )
                )

            )

            xg_home = get_stat(
                hs,
                "expected_goals"
            )

            xg_away = get_stat(
                as_,
                "expected_goals"
            )

            xg = 0

            try:

                if xg_home:
                    xg += float(xg_home)

                if xg_away:
                    xg += float(xg_away)

            except:
                xg = 0

            # =====================================
            # PRESSURE
            # =====================================

            possession_pressure = 0

            if (
                possession_home >= 60
                or possession_away >= 60
            ):

                possession_pressure = 10

            pass_pressure = 0

            if passes >= 700:
                pass_pressure = 10

            elif passes >= 500:
                pass_pressure = 5

            # =====================================
            # MOMENTUM ENGINE
            # =====================================

            momentum = (

                total_shots * 3 +

                shots_on_goal * 4 +

                corners * 2 +

                possession_pressure +

                pass_pressure

            )

            # =====================================
            # TRIGGER SCORE
            # =====================================

            trigger_score = 0

            if total_shots >= 10:
                trigger_score += 20

            if total_shots >= 14:
                trigger_score += 10

            if shots_on_goal >= 4:
                trigger_score += 20

            if shots_on_goal >= 6:
                trigger_score += 10

            if corners >= 6:
                trigger_score += 15

            if corners >= 9:
                trigger_score += 10

            if momentum >= 55:
                trigger_score += 20

            if momentum >= 75:
                trigger_score += 10

            if xg >= 1.2:
                trigger_score += 10

            # =====================================
            # LATE GAME BOOST
            # =====================================

            required_score = 60

            if minute >= 75:
                required_score = 50

            # =====================================
            # DEBUG
            # =====================================

            log(

                "LIVE",

                match_name,

                "MIN", minute,

                "GOALS", total_goals,

                "SOG", shots_on_goal,

                "TS", total_shots,

                "CORNERS", corners,

                "PASSES", passes,

                "XG", xg,

                "MOMENTUM", momentum,

                "TRIGGER", trigger_score

            )

            # =====================================
            # FINAL TRIGGER
            # =====================================

            trigger = False

            if (
                minute >= 60
                and total_goals <= 1
                and trigger_score >= required_score
            ):

                trigger = True

            # =====================================
            # DEBUG FAIL
            # =====================================

            if not trigger:

                if minute < 60:
                    log("FAIL MINUTE")

                if total_goals > 1:
                    log("FAIL GOALS")

                if trigger_score < required_score:
                    log(
                        "FAIL SCORE",
                        trigger_score,
                        required_score
                    )

            # =====================================
            # SEND SIGNAL
            # =====================================

            if trigger:

                if not triggered_matches.get(
                    fixture_id
                ):

                    triggered_matches[
                        fixture_id
                    ] = True

                    send(

                        f"⚡ OVER 1.5 ST\n\n"

                        f"{match_name}\n"

                        f"🕒 {minute}'\n"

                        f"⚽ Goals {total_goals}\n\n"

                        f"🎯 SOG {shots_on_goal}\n"
                        f"📈 Total Shots {total_shots}\n"
                        f"🚩 Corners {corners}\n"
                        f"🧠 Momentum {momentum}\n"
                        f"🔥 Trigger Score {trigger_score}"

                    )

                    log(
                        "TRIGGERED",
                        match_name
                    )

        except Exception as e:

            log("LIVE ERROR", e)

# =========================================================
# LOOP
# =========================================================

def loop():

    while True:

        try:

            now = datetime.now(tz)

            if (
                now.hour == 11
                and 30 <= now.minute <= 35
            ):

                selezione_pro()

            live_scan()

            time.sleep(LIVE_INTERVAL)

        except Exception as e:

            log("LOOP ERROR", e)

            time.sleep(10)

# =========================================================
# TELEGRAM
# =========================================================

@bot.message_handler(func=lambda m: True)
def handle(msg):

    global last_chat_id

    last_chat_id = msg.chat.id

    text = normalize(msg.text)

    # =====================================================
    # START
    # =====================================================

    if text.startswith("/start"):

        bot.reply_to(

            msg,

            "🤖 BOT TRADER PRO ELITE ULTRA ONLINE"

        )

    # =====================================================
    # OGGI
    # =====================================================

    elif text.startswith("/oggi"):

        selezione_pro()

    # =====================================================
    # TODAY
    # =====================================================

    elif text.startswith("/today"):

        if not selected_matches:

            bot.reply_to(
                msg,
                "Nessuna partita attiva"
            )

        else:

            txt = (
                "📅 PARTITE ATTIVE\n\n"
            )

            for _, v in selected_matches.items():

                txt += (

                    f"{v['home']} - "
                    f"{v['away']}\n"

                    f"{v['league']}\n"

                    f"🕒 {v['kickoff']}\n"

                    f"📈 Score "
                    f"{v['score']}\n\n"

                )

            bot.reply_to(
                msg,
                txt
            )

    # =====================================================
    # API
    # =====================================================

    elif text.startswith("/api"):

        bot.reply_to(

            msg,

            f"📡 API CALLS: "
            f"{api_requests}"

        )

    # =====================================================
    # DEBUG
    # =====================================================

    elif text.startswith("/debug"):

        txt = (

            "🧠 DEBUG STATUS\n\n"

            f"Selected: "
            f"{len(selected_matches)}\n"

            f"Triggered: "
            f"{len(triggered_matches)}\n"

            f"API Calls: "
            f"{api_requests}\n"

            f"Debug Mode: "
            f"{DEBUG_MODE}"

        )

        bot.reply_to(
            msg,
            txt
        )

# =========================================================
# START
# =========================================================

print(
    "🚀 BOT TRADER PRO ELITE ULTRA STARTED"
)

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(
    skip_pending=True
)
