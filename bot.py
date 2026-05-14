# =========================================================
# BOT TRADER PRO ELITE ULTRA
# QUADRUPLE LEAGUES + SMART PREMATCH ENGINE
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

BASE_BANKROLL = 100.0

# =========================================================
# VALUE ODDS
# =========================================================

MIN_VALUE_ODDS = 1.55
MAX_VALUE_ODDS = 2.40

# =========================================================
# RISK
# =========================================================

MAX_OPEN_BETS = 3

# =========================================================
# LEAGUES (QUADRUPLICATE)
# =========================================================

LEAGUES = [

    # =====================================
    # TOP EUROPE
    # =====================================

    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1

    # =====================================
    # OFFENSIVE EUROPE
    # =====================================

    88,   # Eredivisie
    94,   # Portugal
    144,  # Belgium
    207,  # Switzerland
    197,  # Denmark
    119,  # Norway
    113,  # Sweden
    179,  # Finland
    203,  # Turkey
    218,  # Czech
    235,  # Saudi
    98,   # Japan
    292,  # Korea
    253,  # MLS
    188,  # Australia

    # =====================================
    # SECOND DIVISIONS
    # =====================================

    72,73,74,
    79,141,136,
    62,244,

    # =====================================
    # EXTRA EUROPE
    # =====================================

    103,104,105,
    106,107,108,
    109,110,111,
    112,114,115,
    116,117,118,
    120,121,122,
    123,124,125,
    126,127,128,

    # =====================================
    # SOUTH AMERICA
    # =====================================

    71,129,130,
    131,132,133,
    134,265,266,
    267,268,269,

    # =====================================
    # EAST EUROPE
    # =====================================

    219,220,221,
    222,223,224,
    225,226,227,
    228,229,230,

    # =====================================
    # AFRICA / MIDDLE EAST
    # =====================================

    236,237,238,
    239,240,241,
    242,243,245,

    # =====================================
    # ASIA
    # =====================================

    307,308,309,
    310,311,312,
    313,314,315,

    # =====================================
    # CENTRAL AMERICA
    # =====================================

    270,271,272,
    273,274,275,

    # =====================================
    # EXTRA
    # =====================================

    143,145,146,
    147,148,149,
    150,151,152,
    153,154,155,
    156,157,158,
    159,160,161,
    162,163,164,
    165,166,167,

    # =====================================
    # ULTRA EXTRA
    # =====================================

    168,169,170,
    171,172,173,
    174,175,176,
    177,178,180,
    181,182,183,
    184,185,186,
    187,189,190,
    191,192,193,
    194,195,196
]

# =========================================================
# OFFENSIVE PRIORITY
# =========================================================

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
    203,
    235
]

# =========================================================
# GLOBAL
# =========================================================

last_chat_id = None

api_requests = 0

selected_matches = {}

last_day = None

cache = {}
team_stats_cache = {}

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
# UTILS
# =========================================================

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

        except:
            pass

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

        print("API ERROR", e)

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
# PREMATCH ODDS
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
# DEFENSIVE FILTER
# =========================================================

def defensive_penalty(avg):

    if avg < 1.8:
        return -50

    if avg < 2.2:
        return -20

    return 0

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

        # =====================================
        # LEAGUE BONUS
        # =====================================

        if league_id in OFFENSIVE_PRIORITY:
            score += 50

        # =====================================
        # TIME BONUS
        # =====================================

        kickoff = datetime.fromisoformat(

            match["fixture"]["date"].replace(
                "Z",
                "+00:00"
            )

        ).astimezone(tz)

        if 17 <= kickoff.hour <= 20:
            score += 20

        # =====================================
        # ODDS FILTER
        # =====================================

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

        # =====================================
        # TEAM STATS
        # =====================================

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

        # =====================================
        # DEFENSIVE FILTER
        # =====================================

        score += defensive_penalty(
            home_stats["total_avg"]
        )

        score += defensive_penalty(
            away_stats["total_avg"]
        )

        # =====================================
        # RECENT GOALS
        # =====================================

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

        print("SCORE ERROR", e)

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

    # =====================================
    # FAST FILTER
    # =====================================

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

    # =====================================
    # SHORTLIST
    # =====================================

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    shortlist = [

        x[1]

        for x in candidates[:40]

    ]

    # =====================================
    # ADVANCED ANALYSIS
    # =====================================

    scored = []

    for m in shortlist:

        s = score_match(m)

        scored.append((s, m))

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    top = scored[:3]

    # =====================================
    # OUTPUT
    # =====================================

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

        cursor.execute("""

        INSERT INTO selections (
            match_name,
            league,
            score,
            created_at
        )

        VALUES (?,?,?,?)

        """, (

            f"{home} - {away}",
            league,
            score,
            datetime.now().isoformat()

        ))

        conn.commit()

        msg += (

            f"⚽ {home} - {away}\n"
            f"🏆 {league}\n"
            f"🕒 {kickoff}\n"
            f"📈 Score: {score}\n\n"

        )

    send(msg)

# =========================================================
# TELEGRAM
# =========================================================

@bot.message_handler(func=lambda m: True)
def handle(msg):

    global last_chat_id

    last_chat_id = msg.chat.id

    text = normalize(msg.text)

    # =====================================
    # START
    # =====================================

    if text == "/start":

        bot.reply_to(

            msg,
            "🤖 BOT TRADER PRO ELITE ULTRA ATTIVO"

        )

    # =====================================
    # TODAY
    # =====================================

    elif text == "/today":

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

    # =====================================
    # OGGI
    # =====================================

    elif text == "/oggi":

        selezione_pro()

    # =====================================
    # API
    # =====================================

    elif text == "/api":

        bot.reply_to(

            msg,
            f"📡 API Calls: "
            f"{api_requests}"

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

            time.sleep(60)

        except Exception as e:

            print("LOOP ERROR", e)

            time.sleep(10)

# =========================================================
# START
# =========================================================

print(
    "🚀 BOT TRADER PRO ELITE ULTRA AVVIATO"
)

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(
    skip_pending=True
)
