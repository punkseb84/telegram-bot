# =========================================================
# BOT TRADER PRO ELITE AI
# OPTIMIZED VERSION
# =========================================================

import telebot
from telebot import types

import requests
import sqlite3
import threading
import time
import os

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

coverage_memory = {}

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
            timeout=20
        )

        api_requests += 1

        return r.json()

    except Exception as e:

        log("API ERROR", e)

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
# LIVE ODDS CACHE
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

    cache_key = (
        f"{today}_{league_id}_{team_id}"
    )

    if cache_key in team_stats_cache:
        return team_stats_cache[cache_key]

    url = (

        f"https://v3.football.api-sports.io/"
        f"teams/statistics?"
        f"league={league_id}&"
        f"season=2026&"
        f"team={team_id}"

    )

    data = api_call(url)

    team_stats_cache[cache_key] = data

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

                name = bet.get(
                    "name",
                    ""
                )

                if "Over/Under" in name:

                    values = bet.get(
                        "values",
                        []
                    )

                    for v in values:

                        value = v.get(
                            "value",
                            ""
                        )

                        odd = v.get(
                            "odd",
                            None
                        )

                        if "Over 1.5" in value:

                            try:
                                return float(odd)
                            except:
                                continue

        return None

    except:
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

        return (gf + ga) / played

    except:
        return 2

# =========================================================
# COVERAGE RATE
# =========================================================

def get_coverage_bonus(league_id):

    cursor.execute("""

    SELECT

        matches_checked,
        stats_available

    FROM league_coverage

    WHERE league_id = ?

    """, (league_id,))

    row = cursor.fetchone()

    if not row:
        return 0

    checked = row[0]
    available = row[1]

    if checked < 5:
        return 0

    rate = (
        available / checked
    ) * 100

    if rate >= 90:
        return 40

    elif rate >= 75:
        return 25

    elif rate <= 50:
        return -30

    return 0

# =========================================================
# UPDATE COVERAGE
# =========================================================

def update_coverage(

    league_id,
    league_name,
    stats_found

):

    cursor.execute("""

    SELECT

        matches_checked,
        stats_available

    FROM league_coverage

    WHERE league_id = ?

    """, (league_id,))

    row = cursor.fetchone()

    if row:

        checked = row[0] + 1
        available = row[1]

        if stats_found:
            available += 1

        cursor.execute("""

        UPDATE league_coverage

        SET

            matches_checked = ?,
            stats_available = ?

        WHERE league_id = ?

        """, (

            checked,
            available,
            league_id

        ))

    else:

        checked = 1
        available = 1 if stats_found else 0

        cursor.execute("""

        INSERT INTO league_coverage (

            league_id,
            league_name,
            matches_checked,
            stats_available

        )

        VALUES (?, ?, ?, ?)

        """, (

            league_id,
            league_name,
            checked,
            available

        ))

    conn.commit()

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

        coverage_bonus = (
            get_coverage_bonus(
                league_id
            )
        )

        score += coverage_bonus

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

    except:
        return 0

# =========================================================
# PREMATCH
# =========================================================

def selezione_pro():

    global selected_matches
    global last_day

    today = datetime.now(tz).date()

    if last_day == today:
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

    scored = []

    now = datetime.now(tz)

    for m in matches:

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

    top = scored[:MAX_SELECTED_MATCHES]

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
            "league_id": (
                m["league"]["id"]
            ),
            "kickoff": kickoff,
            "score": score

        }

        txt += (

            f"⚽ {home} - {away}\n"
            f"🏆 {league}\n"
            f"🕒 {kickoff}\n"
            f"📈 Score {score}\n\n"

        )

    send(txt)

# =========================================================
# SAVE TRIGGER
# =========================================================

def save_trigger(

    fixture_id,
    match_name,
    league,

    minute,

    sog,
    total_shots,
    corners,

    xg,
    momentum,
    trigger_score,

    goals_at_trigger,

    live_odd

):

    cursor.execute("""

    INSERT INTO trigger_history (

        fixture_id,

        match_name,

        league,

        minute,

        sog,

        total_shots,

        corners,

        xg,

        momentum,

        trigger_score,

        goals_at_trigger,

        live_odd,

        created_at

    )

    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        fixture_id,

        match_name,

        league,

        minute,

        sog,

        total_shots,

        corners,

        xg,

        momentum,

        trigger_score,

        goals_at_trigger,

        live_odd,

        str(datetime.now())

    ))

    conn.commit()

# =========================================================
# RESULT CHECKER
# =========================================================

def check_finished_matches():

    cursor.execute("""

    SELECT

        id,
        fixture_id,
        goals_at_trigger

    FROM trigger_history

    WHERE result_checked = 0

    LIMIT 5

    """)

    rows = cursor.fetchall()

    for row in rows:

        row_id = row[0]

        fixture_id = row[1]

        goals_at_trigger = row[2]

        try:

            data = api_call(

                f"https://v3.football.api-sports.io/"
                f"fixtures?id={fixture_id}"

            )

            response = data.get(
                "response",
                []
            )

            if not response:
                continue

            match = response[0]

            status = (
                match["fixture"]
                ["status"]["short"]
            )

            if status != "FT":
                continue

            home_goals = (
                match["goals"]["home"] or 0
            )

            away_goals = (
                match["goals"]["away"] or 0
            )

            final_goals = (
                home_goals + away_goals
            )

            final_score = (
                f"{home_goals}-{away_goals}"
            )

            goal_after_trigger = 0

            if final_goals > goals_at_trigger:
                goal_after_trigger = 1

            cursor.execute("""

            UPDATE trigger_history

            SET

                final_goals = ?,

                goal_after_trigger = ?,

                final_score = ?,

                result_checked = 1

            WHERE id = ?

            """, (

                final_goals,

                goal_after_trigger,

                final_score,

                row_id

            ))

            conn.commit()

        except Exception as e:

            log(
                "RESULT ERROR",
                e
            )

# =========================================================
# LIVE ENGINE
# =========================================================

def live_scan():

    live = api_call(

        "https://v3.football.api-sports.io/"
        "fixtures?live=all"

    )

    matches = live.get(
        "response",
        []
    )

    for m in matches:

        try:

            fixture_id = (
                m["fixture"]["id"]
            )

            if fixture_id not in selected_matches:
                continue

            minute = (
                m["fixture"]["status"]
                ["elapsed"]
            )

            if not minute:
                continue

            league_id = (
                selected_matches[
                    fixture_id
                ]["league_id"]
            )

            league_name = (
                selected_matches[
                    fixture_id
                ]["league"]
            )

            home = (
                m["teams"]["home"]["name"]
            )

            away = (
                m["teams"]["away"]["name"]
            )

            match_name = (
                f"{home} - {away}"
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

            stats_data = get_fixture_statistics(
                fixture_id
            )

            response = stats_data.get(
                "response",
                []
            )

            # =====================================================
            # COVERAGE TRACKING
            # =====================================================

            if len(response) < 2:

                update_coverage(

                    league_id,
                    league_name,
                    False

                )

                log(
                    "NO STATS",
                    match_name
                )

                continue

            update_coverage(

                league_id,
                league_name,
                True

            )

            hs = response[0]["statistics"]
            as_ = response[1]["statistics"]

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
                pass

            momentum = (

                total_shots * 3 +

                shots_on_goal * 5 +

                corners * 2

            )

            # =====================================================
            # HARD FILTERS
            # =====================================================

            if shots_on_goal < 4:
                continue

            trigger_score = 0

            # =====================================================
            # SCORE ENGINE
            # =====================================================

            if total_shots >= 10:
                trigger_score += 20

            if total_shots >= 14:
                trigger_score += 10

            if shots_on_goal >= 4:
                trigger_score += 25

            if shots_on_goal >= 6:
                trigger_score += 15

            if corners >= 6:
                trigger_score += 15

            if corners >= 9:
                trigger_score += 10

            if momentum >= 60:
                trigger_score += 20

            if momentum >= 80:
                trigger_score += 10

            # =====================================================
            # XG BONUS ONLY
            # =====================================================

            if xg >= 1.2:
                trigger_score += 15

            if xg >= 1.8:
                trigger_score += 10

            if xg >= 2.5:
                trigger_score += 10

            # =====================================================
            # ODDS ONLY FOR GOOD MATCHES
            # =====================================================

            live_odd = None

            if (

                minute >= 60

                and trigger_score >= 40

            ):

                odds_data = get_live_odds(
                    fixture_id
                )

                live_odd = extract_over15_odds(
                    odds_data
                )

                odds_score = odds_pressure_score(
                    live_odd
                )

                trigger_score += odds_score

            # =====================================================
            # DEAD MARKET FILTER
            # =====================================================

            if live_odd:

                if live_odd >= 3.50:
                    continue

            required_score = 65

            if minute >= 75:
                required_score = 60

            if minute >= 82:
                required_score = 55

            log(

                "LIVE",

                match_name,

                "MIN", minute,

                "GOALS", total_goals,

                "SOG", shots_on_goal,

                "TS", total_shots,

                "CORNERS", corners,

                "XG", xg,

                "MOMENTUM", momentum,

                "ODD", live_odd,

                "TRIGGER", trigger_score

            )

            trigger = False

            if (

                minute >= 60

                and total_goals <= 1

                and trigger_score >= required_score

            ):

                trigger = True

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
                        f"📊 xG {round(xg,2)}\n"
                        f"🧠 Momentum {momentum}\n"
                        f"💰 Live Odd {live_odd}\n"
                        f"🔥 Trigger Score {trigger_score}"

                    )

                    save_trigger(

                        fixture_id,
                        match_name,

                        selected_matches[
                            fixture_id
                        ]["league"],

                        minute,

                        shots_on_goal,
                        total_shots,
                        corners,

                        xg,
                        momentum,
                        trigger_score,

                        total_goals,

                        live_odd

                    )

        except Exception as e:

            log(
                "LIVE ERROR",
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

            check_finished_matches()

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

    # =====================================================
    # START
    # =====================================================

    if text.startswith("/start"):

        bot.reply_to(

            msg,

            "🚀 BOT TRADER PRO ELITE AI ONLINE"

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
    # PERFORMANCE
    # =====================================================

    elif text.startswith("/performance"):

        cursor.execute("""

        SELECT

            COUNT(*),

            SUM(goal_after_trigger)

        FROM trigger_history

        WHERE result_checked = 1

        """)

        row = cursor.fetchone()

        total = row[0] or 0

        wins = row[1] or 0

        if total == 0:

            bot.reply_to(
                msg,
                "Nessun dato"
            )

        else:

            rate = round(
                wins / total * 100,
                2
            )

            bot.reply_to(

                msg,

                f"📊 PERFORMANCE\n\n"

                f"Triggers: {total}\n"
                f"Goals After Trigger: {wins}\n"
                f"Hit Rate: {rate}%"

            )

    # =====================================================
    # ODDS PERFORMANCE
    # =====================================================

    elif text.startswith("/oddsperf"):

        cursor.execute("""

        SELECT

            COUNT(*),

            AVG(live_odd),

            SUM(goal_after_trigger)

        FROM trigger_history

        WHERE

            result_checked = 1

            AND live_odd IS NOT NULL

        """)

        row = cursor.fetchone()

        total = row[0] or 0

        avg_odd = round(
            row[1] or 0,
            2
        )

        wins = row[2] or 0

        if total == 0:

            bot.reply_to(
                msg,
                "Nessun dato"
            )

        else:

            rate = round(
                wins / total * 100,
                2
            )

            bot.reply_to(

                msg,

                f"💰 ODDS PERFORMANCE\n\n"

                f"Triggers: {total}\n"

                f"Average Odd: {avg_odd}\n"

                f"Goals After Trigger: {wins}\n"

                f"Hit Rate: {rate}%"

            )

    # =====================================================
    # COVERAGE
    # =====================================================

    elif text.startswith("/coverage"):

        cursor.execute("""

        SELECT

            league_name,
            matches_checked,
            stats_available

        FROM league_coverage

        ORDER BY stats_available DESC

        LIMIT 10

        """)

        rows = cursor.fetchall()

        if not rows:

            bot.reply_to(
                msg,
                "Nessun dato"
            )

        else:

            txt = (
                "📡 LIVE COVERAGE\n\n"
            )

            for r in rows:

                league = r[0]
                checked = r[1]
                available = r[2]

                rate = round(
                    available / checked * 100,
                    1
                )

                txt += (

                    f"{league}\n"

                    f"Coverage: {rate}%\n\n"

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
    "🚀 BOT TRADER PRO ELITE AI OPTIMIZED STARTED"
)

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(
    skip_pending=True
)
