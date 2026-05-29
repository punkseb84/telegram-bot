# =========================================================
# football_api.py
# BOT TRADER PRO ELITE AI
# =========================================================

import os
import time
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =========================================================
# CONFIG
# =========================================================

API_KEY = os.getenv("API_KEY")

# =========================================================
# GLOBALS
# =========================================================

api_requests = 0

stats_cache = {}
odds_cache = {}
team_stats_cache = {}

# =========================================================
# LOG
# =========================================================

DEBUG_MODE = True

def log(*args):

    if DEBUG_MODE:
        print("[API]", *args)

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
# API COUNTER
# =========================================================

def get_api_requests():

    return api_requests

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

def safe_int(value):

    try:

        if value is None:
            return 0

        if isinstance(value, str):
            value = value.replace("%", "")

        return int(float(value))

    except:
        return 0

# =========================================================
# GET STAT
# =========================================================

def get_stat(stats, stat_name):

    for stat in stats:

        if stat["type"] == stat_name:

            return stat["value"]

    return None

# =========================================================
# FIXTURE STATISTICS
# CACHE 20 sec
# =========================================================

def get_fixture_statistics(fixture_id):

    now = time.time()

    if fixture_id in stats_cache:

        ts, data = stats_cache[fixture_id]

        if now - ts < 20:

            return data

    url = (

        "https://v3.football.api-sports.io/"
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
# LIVE ODDS
# CACHE 90 sec
# =========================================================

def get_live_odds(fixture_id):

    now = time.time()

    if fixture_id in odds_cache:

        ts, data = odds_cache[fixture_id]

        if now - ts < 90:

            return data

    url = (

        "https://v3.football.api-sports.io/"
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
# TEAM STATISTICS
# SEASON DYNAMIC
# =========================================================

def get_team_stats(

    team_id,
    league_id,
    season

):

    key = (

        f"{league_id}_"
        f"{season}_"
        f"{team_id}"

    )

    if key in team_stats_cache:

        return team_stats_cache[key]

    url = (

        "https://v3.football.api-sports.io/"
        "teams/statistics?"

        f"league={league_id}&"
        f"season={season}&"
        f"team={team_id}"

    )

    data = api_call(url)

    team_stats_cache[key] = data

    return data

# =========================================================
# EXTRACT OVER 1.5 ODDS
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
            .get(
                "bookmakers",
                []
            )

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

                for value in bet.get(
                    "values",
                    []
                ):

                    if "Over 1.5" in value.get(
                        "value",
                        ""
                    ):

                        try:

                            return float(
                                value.get(
                                    "odd"
                                )
                            )

                        except:
                            pass

        return None

    except Exception as e:

        log(
            "ODDS PARSE ERROR",
            e
        )

        return None

# =========================================================
# ODDS PRESSURE SCORE
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
# CACHE INFO
# =========================================================

def cache_info():

    return {

        "stats_cache":
        len(stats_cache),

        "odds_cache":
        len(odds_cache),

        "team_cache":
        len(team_stats_cache)

    }

# =========================================================
# CLEAR CACHE
# =========================================================

def clear_cache():

    stats_cache.clear()

    odds_cache.clear()

    team_stats_cache.clear()

    log("CACHE CLEARED")
