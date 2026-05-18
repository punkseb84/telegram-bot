# =========================================================
# BOT TRADER PRO ELITE ULTRA + DEBUG
# VERSIONE COMPLETA
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

START_HOUR = 14
END_HOUR = 21

MIN_VALUE_ODDS = 1.55
MAX_VALUE_ODDS = 2.40

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
    224,225,226,

    235,236,237,
    238,239,240,

    307,308,309,
    310,311,312,

    71,128,129,
    130,131,132,
    133,134,

    265,266,267,
    268,269,270
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

tracked_live = {}

cache = {}
team_stats_cache = {}

last_day = None

# =========================================================
# DATABASE
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
    league TEXT,
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
        "API calls"
    ),

    types.BotCommand(
        "debug",
        "Debug live"
    )

])

# =========================================================
# UTILS
# =========================================================

def log(*args):

    if DEBUG_MODE:
        print("[DEBUG]", *args)

def normalize(text):

    return text.split("@")[0].strip().lower()

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
# CACHE
# =========================================================

def cached_api_call(url, ttl=3600):

    now = time.time()

    if url in cache:

        ts, data = cache[url]

        if now - ts < ttl:
            return data

    data = api_call(url)

    cache[url] = (
        now,
        data
    )

    return data

# =========================================================
# TEAM STATS
# =========================================================

def get_team_stats(team_id, league_id):

    key = f"{team_id}_{league_id}"

    if key in team_stats_cache:

        ts, data = team_stats_cache[key]

        if time.time() - ts < 86400:
            return data

    url = (

        f"https://v3.football.api-sports.io/"
        f"teams/statistics?"
        f"league={league_id}&"
        f"season=2026&"
        f"team={team_id}"

    )

    data = cached_api_call(
        url,
        ttl=86400
    )

    team_stats_cache[key] = (
        time.time(),
        data
    )

    return data

# =========================================================
# ANALYZE TEAM
# =========================================================

def analyze_team(team_data):

    try:

        played = (
            team_data["response"]
            ["fixtures"]["played"]["total"]
        )

        goals_for = (
            team_data["response"]
            ["goals"]["for"]["total"]["total"]
        )

        goals_against = (
            team_data["response"]
            ["goals"]["against"]["total"]["total"]
        )

        avg_for = goals_for / played
        avg_against = goals_against / played

        total_avg = avg_for + avg_against

        return {

            "avg_for": avg_for,
            "avg_against": avg_against,
            "total_avg": total_avg

        }

    except:

        return {

            "avg_for": 1,
            "avg_against": 1,
            "total_avg": 2

        }

# =========================================================
# ODDS
# =========================================================

def get_prematch_odds(fixture_id):

    try:

        data = cached_api_call(

            f"https://v3.football.api-sports.io/"
            f"odds?fixture={fixture_id}",

            ttl=3600
        )

        bookmakers = (
            data["response"][0]
            ["bookmakers"]
        )

        for bookmaker in bookmakers:

            for bet in bookmaker["bets"]:

                if bet["name"] == "Over/Under":

                    for value in bet["values"]:

                        if value["value"] == "Over 2.5":

                            return float(
                                value["odd"]
                            )

    except:
        return None

    return None

# =========================================================
# RECENT GOALS
# =========================================================

def get_recent_goals(team_id):

    try:

        data = cached_api_call(

            f"https://v3.football.api-sports.io/"
            f"fixtures?team={team_id}&last=5",

            ttl=3600
        )

        matches = data["response"]

        total = 0

        for m in matches:

            total += (
                m["goals"]["home"] +
                m["goals"]["away"]
            )

        return total / len(matches)

    except:
        return 2

# =========================================================
# SCORE MATCH
# =========================================================

def score_match(match):

    try:

        score = 0

        fixture_id = match["fixture"]["id"]

        league_id = match["league"]["id"]

        home_id = (
            match["teams"]["home"]["id"]
        )

        away_id = (
            match["teams"]["away"]["id"]
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

        odds = get_prematch_odds(
            fixture_id
        )

        if odds:

            if odds <= 1.65:
                score += 50

            elif odds <= 1.80:
                score += 35

            elif odds <= 2:
                score += 15

            elif odds >= 2.5:
                score -= 40

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

        total_avg = (

            home_stats["total_avg"] +
            away_stats["total_avg"]

        )

        score += total_avg * 15

        recent_home = get_recent_goals(
            home_id
        )

        recent_away = get_recent_goals(
            away_id
        )

        score += (
            recent_home +
            recent_away
        ) * 6

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
            "⚠️ Partite già selezionate oggi"
        )

        return

    last_day = today

    selected_matches.clear()

    data = api_call(

        f"https://v3.football.api-sports.io/"
        f"fixtures?date={today}"

    )

    now = datetime.now(tz)

    candidates = []

    for m in data.get("response", []):

        try:

            league_id = m["league"]["id"]

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

            base = 0

            if league_id in OFFENSIVE_PRIORITY:
                base += 50

            if 17 <= kickoff.hour <= 20:
                base += 20

            candidates.append(
                (base, m)
            )

        except:
            continue

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    shortlist = [

        x[1]

        for x in candidates[:40]

    ]

    scored = []

    for m in shortlist:

        s = score_match(m)

        scored.append((s, m))

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    top = scored[:3]

    msg = (
        "🔥 PARTITE SELEZIONATE\n\n"
    )

    for score, m in top:

        match_id = (
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

        selected_matches[match_id] = {

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

    log("SELECTED", selected_matches)

# =========================================================
# GET STAT
# =========================================================

def get_stat(stats, name):

    for s in stats:

        if s["type"] == name:
            return s["value"] or 0

    return 0

# =========================================================
# LIVE ENGINE + DEBUG
# =========================================================

def live_scan():

    data = api_call(

        "https://v3.football.api-sports.io/"
        "fixtures?live=all"

    )

    matches = data.get("response", [])

    log("LIVE FOUND", len(matches))

    for m in matches:

        try:

            fixture_id = m["fixture"]["id"]

            if fixture_id not in selected_matches:
                continue

            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]

            match_name = f"{home} - {away}"

            log("TRACKING", match_name)

            minute = (
                m["fixture"]["status"]["elapsed"]
            )

            home_goals = (
                m["goals"]["home"] or 0
            )

            away_goals = (
                m["goals"]["away"] or 0
            )

            total_goals = (
                home_goals + away_goals
            )

            stats = m.get("statistics")

            if not stats:

                log(
                    "NO STATS",
                    match_name
                )

                continue

            try:

                hs = stats[0]["statistics"]
                as_ = stats[1]["statistics"]

            except Exception as e:

                log(
                    "STATS ERROR",
                    match_name,
                    e
                )

                continue

            try:

                xg = (

                    float(
                        get_stat(
                            hs,
                            "Expected Goals (xG)"
                        )
                    )

                    +

                    float(
                        get_stat(
                            as_,
                            "Expected Goals (xG)"
                        )
                    )

                )

            except:
                xg = 0

            try:

                shots = (

                    int(
                        get_stat(
                            hs,
                            "Shots on Goal"
                        )
                    )

                    +

                    int(
                        get_stat(
                            as_,
                            "Shots on Goal"
                        )
                    )

                )

            except:
                shots = 0

            try:

                attacks = (

                    int(
                        get_stat(
                            hs,
                            "Dangerous Attacks"
                        )
                    )

                    +

                    int(
                        get_stat(
                            as_,
                            "Dangerous Attacks"
                        )
                    )

                )

            except:
                attacks = 0

            try:

                corners = (

                    int(
                        get_stat(
                            hs,
                            "Corner Kicks"
                        )
                    )

                    +

                    int(
                        get_stat(
                            as_,
                            "Corner Kicks"
                        )
                    )

                )

            except:
                corners = 0

            momentum = (
                attacks +
                shots * 2
            )

            log(

                "LIVE",

                match_name,

                "MIN", minute,

                "GOALS", total_goals,

                "XG", xg,

                "SHOTS", shots,

                "ATTACKS", attacks,

                "MOMENTUM", momentum,

                "CORNERS", corners

            )

            trigger = False

            if (
                minute >= 60
                and total_goals <= 1
                and xg >= 1.2
                and momentum >= 70
                and shots >= 5
            ):

                trigger = True

            log(
                "TRIGGER CHECK",
                match_name,
                trigger
            )

            if trigger:

                if not triggered_matches.get(fixture_id):

                    triggered_matches[
                        fixture_id
                    ] = True

                    send(

                        f"⚡ OVER 1.5 ST\n\n"

                        f"{match_name}\n"

                        f"🕒 {minute}'\n"

                        f"⚽ Goals {total_goals}\n"

                        f"📈 xG {xg}\n"

                        f"🎯 Shots {shots}\n"

                        f"⚡ Momentum {momentum}\n"

                        f"🚩 Corners {corners}"

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

            time.sleep(30)

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

            "🤖 BOT TRADER PRO ELITE ULTRA + DEBUG ATTIVO"

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

            f"📡 API Calls: "
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
    "🚀 BOT TRADER PRO ELITE ULTRA + DEBUG AVVIATO"
)

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(
    skip_pending=True
)
