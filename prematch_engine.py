# =========================================================
# prematch_engine.py
# BOT TRADER PRO ELITE AI
# =========================================================

from datetime import datetime
from zoneinfo import ZoneInfo

from football_api import (
    api_call,
    get_team_stats
)

from coverage_engine import (
    apply_coverage_bonus
)

# =========================================================
# CONFIG
# =========================================================

tz = ZoneInfo("Europe/Rome")

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

# =========================================================
# OFFENSIVE LEAGUES
# =========================================================

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
# ANALYZE TEAM
# =========================================================

def analyze_team(data):

    try:

        response = data.get(
            "response",
            {}
        )

        played = (
            response["fixtures"]
            ["played"]
            ["total"]
        )

        gf = (
            response["goals"]
            ["for"]
            ["total"]
            ["total"]
        )

        ga = (
            response["goals"]
            ["against"]
            ["total"]
            ["total"]
        )

        if played == 0:
            return 2

        return round(
            (gf + ga) / played,
            2
        )

    except Exception as e:

        print(
            "[TEAM ANALYZE ERROR]",
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

        season = (
            match["league"]["season"]
        )

        home_id = (
            match["teams"]["home"]["id"]
        )

        away_id = (
            match["teams"]["away"]["id"]
        )

        # ------------------------
        # LEAGUE BONUS
        # ------------------------

        if league_id in OFFENSIVE_PRIORITY:

            score += 50

        # ------------------------
        # TEAM STATS
        # ------------------------

        print(

            "[PREMATCH] ANALYZING",

            home_id,
            away_id,

            league_id,
            season

        )

        home_stats = analyze_team(

            get_team_stats(

                home_id,
                league_id,
                season

            )

        )

        away_stats = analyze_team(

            get_team_stats(

                away_id,
                league_id,
                season

            )

        )

        score += (

            home_stats +
            away_stats

        ) * 10

        # ------------------------
        # COVERAGE BONUS
        # ------------------------

        score = apply_coverage_bonus(

            league_id,
            score

        )

        if score is None:

            return 0

        return round(score, 2)

    except Exception as e:

        print(
            "[MATCH SCORE ERROR]",
            e
        )

        return 0

# =========================================================
# SELECT MATCHES
# =========================================================

def select_matches():

    print(
        "[PREMATCH] START"
    )

    try:

        today = datetime.now(
            tz
        ).date()

        data = api_call(

            "https://v3.football.api-sports.io/"
            f"fixtures?date={today}"

        )

        matches = data.get(
            "response",
            []
        )

        print(

            "[PREMATCH] MATCHES",

            len(matches)

        )

        scored = []

        fallback = []

        now = datetime.now(tz)

        for match in matches:

            try:

                league_id = (
                    match["league"]["id"]
                )

                if league_id not in LEAGUES:
                    continue

                kickoff = datetime.fromisoformat(

                    match["fixture"]["date"]

                    .replace(
                        "Z",
                        "+00:00"
                    )

                ).astimezone(tz)

                if not (

                    START_HOUR

                    <= kickoff.hour

                    <= END_HOUR

                ):
                    continue

                fallback.append(match)

                score = score_match(
                    match
                )

                if score <= 0:
                    continue

                scored.append(

                    (
                        score,
                        match
                    )

                )

            except Exception as e:

                print(
                    "[PREMATCH ERROR]",
                    e
                )

        scored.sort(

            key=lambda x: x[0],

            reverse=True

        )

        selected = scored[
            :MAX_SELECTED_MATCHES
        ]

        # ------------------------
        # FALLBACK
        # ------------------------

        if len(selected) == 0:

            print(
                "[PREMATCH] FALLBACK MODE"
            )

            for match in fallback[
                :MAX_SELECTED_MATCHES
            ]:

                selected.append(

                    (
                        0,
                        match
                    )

                )

        print(

            "[PREMATCH] SELECTED",

            len(selected)

        )

        return selected

    except Exception as e:

        print(
            "[PREMATCH FATAL]",
            e
        )

        return []
