# =========================================================
# BOT TRADER PRO ELITE AI
# FINAL STABLE VERSION
# =========================================================

import telebot
from telebot import types

import requests
import sqlite3
import threading
import time
import os

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

MAX_SELECTED_MATCHES = 3

# =========================================================
# SESSION + RETRY
# =========================================================

session = requests.Session()

retry_strategy = Retry(

    total=3,

    connect=3,

    read=3,

    backoff_factor=1,

    status_forcelist=[
        429,
        500,
        502,
        503,
        504
    ],

    allowed_methods=["GET"]

)

adapter = HTTPAdapter(

    max_retries=retry_strategy,

    pool_connections=50,

    pool_maxsize=50

)

session.mount(
    "https://",
    adapter
)

session.mount(
    "http://",
    adapter
)

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
    112,114,115
]

OFFENSIVE_PRIORITY = [

    88,
    144,
    119,
    113,
    179,
    98,
    39,
    78,
    94,
    197,
    207,
    253
]

# =========================================================
# GLOBALS
# =========================================================

last_chat_id = None

api_requests = 0

selected_matches = {}

triggered_matches = {}

stats_cache = {}

odds_cache = {}

team_stats_cache = {}

live_data_status = {}

last_day = None

# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect(
    "trader.db",
    check_same_thread=False
)

cursor = conn.cursor()

# =========================================================
# TABLES
# =========================================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS trigger_history (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    fixture_id INTEGER,

    match_name TEXT,

    league TEXT,

    minute INTEGER,

    sog INTEGER,

    total_shots INTEGER,

    corners INTEGER,

    xg REAL,

    momentum REAL,

    trigger_score REAL,

    goals_at_trigger INTEGER,

    live_odd REAL,

    final_goals INTEGER DEFAULT NULL,

    goal_after_trigger INTEGER DEFAULT NULL,

    final_score TEXT DEFAULT NULL,

    result_checked INTEGER DEFAULT 0,

    created_at TEXT

)

""")

cursor.execute("""

CREATE TABLE IF NOT EXISTS league_coverage (

    league_id INTEGER PRIMARY KEY,

    league_name TEXT,

    matches_checked INTEGER DEFAULT 0,

    stats_available INTEGER DEFAULT 0

)

""")

conn.commit()

# =========================================================
# COMMANDS
# =========================================================

bot.set_my_commands([

    types.BotCommand(
        "start",
        "Avvia bot"
    ),

    types.BotCommand(
        "oggi",
        "Selezione prematch"
    ),

    types.BotCommand(
        "today",
        "Partite attive"
    ),

    types.BotCommand(
        "performance",
        "Performance"
    ),

    types.BotCommand(
        "oddsperf",
        "Performance odds"
    ),

    types.BotCommand(
        "coverage",
        "Coverage leghe"
    ),

    types.BotCommand(
        "livecheck",
        "Controllo dati live"
    ),

    types.BotCommand(
        "api",
        "API usage"
    ),

    types.BotCommand(
        "debug",
        "Debug"
    )

])

# =========================================================
# LOG
# =========================================================

def log(*args):

    if DEBUG_MODE:
        print("[DEBUG]", *args)

# =========================================================
# SEND
# =========================================================

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

# =========================================================
# NORMALIZE
# =========================================================

def normalize(text):

    return text.split("@")[0].lower().strip()

# =========================================================
# API CALL
# =========================================================

def api_call(url):

    global api_requests

    headers = {

        "x-apisports-key": API_KEY,

        "x-rapidapi-host":
        "v3.football.api-sports.io"

    }

    try:

        r = session.get(

            url,

            headers=headers,

            timeout=20

        )

        api_requests += 1

        time.sleep(0.2)

        return r.json()

    except Exception as e:

        log(
            "API ERROR",
            e
        )

        return {}

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
# GET STAT
# =========================================================

def get_stat(stats, name):

    for s in stats:

        if s["type"] == name:
            return s["value"]

    return None

# =========================================================
# FIXTURE STATS CACHE
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
# ODDS CACHE
# =========================================================

def get_live_odds(fixture_id):

    now = time.time()

    if fixture_id in odds_cache:

        ts, data = odds_cache[fixture_id]

        if now - ts < 90:
            return data

    url = (

        f"https://v3.football.api-sports.io/"
        f"odds/live?"
        f"fixture={fixture_id}"

    )

    data = api_call(url)

    odds_cache[fixture_id] = (
        now,
        data
    )

    return data

# =========================================================
# TEAM STATS CACHE
# =========================================================

def get_team_stats(team_id, league_id):

    today = str(
        datetime.now(tz).date()
    )

    key = (
        f"{today}_{league_id}_{team_id}"
    )

    if key in team_stats_cache:
        return team_stats_cache[key]

    url = (

        f"https://v3.football.api-sports.io/"
        f"teams/statistics?"
        f"league={league_id}&"
        f"season=2026&"
        f"team={team_id}"

    )

    data = api_call(url)

    team_stats_cache[key] = data

    return data

# =========================================================
# EXTRACT ODDS
# =========================================================

def extract_over15_odds(data):

    try:

        response = data.get(
            "response",
            []
        )

        if not response:
            return None

        bookmakers = (
            response[0]
            .get("bookmakers", [])
        )

        for bookmaker in bookmakers:

            bets = bookmaker.get(
                "bets",
                []
            )

            for bet in bets:

                if "Over/Under" not in bet.get(
                    "name",
                    ""
                ):
                    continue

                for v in bet.get(
                    "values",
                    []
                ):

                    if "Over 1.5" in v.get(
                        "value",
                        ""
                    ):

                        try:
                            return float(
                                v.get("odd")
                            )
                        except:
                            pass

        return None

    except Exception as e:

        log(
            "ODDS ERROR",
            e
        )

        return None

# =========================================================
# ODDS SCORE
# =========================================================

def odds_pressure_score(odd):

    if odd is None:
        return 0

    score = 0

    if odd <= 1.40:
        score += 35

    elif odd <= 1.60:
        score += 30

    elif odd <= 1.80:
        score += 25

    elif odd <= 2.00:
        score += 20

    elif odd <= 2.30:
        score += 10

    elif odd >= 3.50:
        score -= 25

    elif odd >= 3.00:
        score -= 15

    return score

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

        if played == 0:
            return 2

        return (gf + ga) / played

    except Exception as e:

        log(
            "TEAM ANALYZE ERROR",
            e
        )

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

        if league_id in OFFENSIVE_PRIORITY:
            score += 50

        kickoff = datetime.fromisoformat(

            match["fixture"]["date"].replace(
                "Z",
                "+00:00"
            )

        ).astimezone(tz)

        if 17 <= kickoff.hour <= 20:
            score += 20

        home_id = (
            match["teams"]["home"]["id"]
        )

        away_id = (
            match["teams"]["away"]["id"]
        )

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

        log(
            "SCORE ERROR",
            e
        )

        return 0

# =========================================================
# PREMATCH
# =========================================================

def selezione_pro(force=False):

    global selected_matches
    global last_day

    today = datetime.now(tz).date()

    print("SELEZIONE START")

    print("LAST DAY", last_day)

    print("TODAY", today)

    if last_day == today and not force:

        print("SELEZIONE SKIPPED")

        return

    last_day = today

    selected_matches.clear()

    data = api_call(

        f"https://v3.football.api-sports.io/"
        f"fixtures?date={today}"

    )

    matches = data.get(
        "response",
        []
    )

    print("MATCHES FOUND", len(matches))

    scored = []

    now = datetime.now(tz)

    for m in matches:

        try:

            home = (
                m["teams"]["home"]["name"]
            )

            away = (
                m["teams"]["away"]["name"]
            )

            print(
                "CHECKING",
                home,
                away
            )

            league_id = (
                m["league"]["id"]
            )

            if league_id not in LEAGUES:

                print("SKIP LEAGUE")

                continue

            kickoff = datetime.fromisoformat(

                m["fixture"]["date"].replace(
                    "Z",
                    "+00:00"
                )

            ).astimezone(tz)

            delta = (
                kickoff - now
            ).total_seconds()

            # allow matches started
            # max 30 minutes ago

            if delta < -1800:

                print("SKIP STARTED")

                continue

            if not (
                START_HOUR <= kickoff.hour <= END_HOUR
            ):

                print("SKIP TIME")

                continue

            score = score_match(m)

            print(
                "MATCH SCORE",
                home,
                away,
                score
            )

            scored.append(
                (score, m)
            )

        except Exception as e:

            print(
                "PREMATCH ERROR",
                e
            )

            continue

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    top = scored[:MAX_SELECTED_MATCHES]

    print("TOP MATCHES", len(top))

    if not top:

        send(
            "⚠ Nessuna partita valida trovata"
        )

        return

    txt = (
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
            "score": score,
            "kickoff": kickoff

        }

        txt += (

            f"⚽ {home} - {away}\n"
            f"🏆 {league}\n"
            f"🕒 {kickoff}\n"
            f"📈 Score {score}\n\n"

        )

    send(txt)

# =========================================================
# LIVE SCAN
# =========================================================

def live_scan():

    try:

        live = api_call(

            "https://v3.football.api-sports.io/"
            "fixtures?live=all"

        )

        matches = live.get(
            "response",
            []
        )

        log(
            "LIVE FOUND",
            len(matches)
        )

    except Exception as e:

        log(
            "LIVE SCAN ERROR",
            e
        )

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

            log(
                "LOOP ERROR",
                e
            )

            time.sleep(10)

# =========================================================
# TELEGRAM
# =========================================================

@bot.message_handler(func=lambda m: True)
def handle(msg):

    global last_chat_id

    last_chat_id = msg.chat.id

    text = normalize(msg.text)

    print("COMMAND:", text)

    # =====================================================
    # START
    # =====================================================

    if text.startswith("/start"):

        bot.reply_to(

            msg,

            "🚀 BOT FINAL STABLE ONLINE"

        )

    # =====================================================
    # OGGI
    # =====================================================

    elif text.startswith("/oggi"):

        selezione_pro(force=True)

    # =====================================================
    # TODAY
    # =====================================================

    elif text.startswith("/today"):

        if not selected_matches:

            bot.reply_to(
                msg,
                "Nessuna partita"
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

            f"Stats Cache: "
            f"{len(stats_cache)}\n"

            f"Odds Cache: "
            f"{len(odds_cache)}\n"

            f"Team Cache: "
            f"{len(team_stats_cache)}"

        )

        bot.reply_to(
            msg,
            txt
        )

# =========================================================
# START
# =========================================================

print(
    "🚀 BOT FINAL STABLE STARTED"
)

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(
    skip_pending=True
)
