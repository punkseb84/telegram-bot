# =========================================================
# live_engine.py
# BOT TRADER PRO ELITE AI
# =========================================================

from datetime import datetime

from football_api import (

    api_call,

    get_fixture_statistics,

    get_live_odds,

    extract_over15_odds,

    get_stat,

    safe_int,

    odds_pressure_score

)

from coverage_engine import (

    register_live_feed,

    feed_quality,

    feed_status

)

from database import (

    save_trigger

)

# =========================================================
# GLOBALS
# =========================================================

triggered_matches = {}

reported_60 = {}

# =========================================================
# MOMENTUM
# =========================================================

def calculate_momentum(

    sog,
    shots,
    corners

):

    return (

        sog * 8 +

        shots * 2 +

        corners * 3

    )

# =========================================================
# REQUIRED SCORE
# =========================================================

def required_score(minute):

    if 60 <= minute <= 69:
        return 70

    if 70 <= minute <= 79:
        return 65

    if 80 <= minute <= 85:
        return 58

    return 999

# =========================================================
# TRIGGER SCORE
# =========================================================

def trigger_score(

    sog,
    shots,
    corners,

    passes,

    xg,

    momentum,

    odd

):

    score = 0

    score += sog * 5

    score += shots * 2

    score += corners * 2

    score += momentum * 0.5

    score += passes / 25

    score += xg * 10

    score += odds_pressure_score(
        odd
    )

    return round(score, 2)

# =========================================================
# LIVE CHECK
# =========================================================

def process_match(

    fixture,

    bot_send,

    league_name

):

    fixture_id = (
        fixture["fixture"]["id"]
    )

    home = (
        fixture["teams"]["home"]["name"]
    )

    away = (
        fixture["teams"]["away"]["name"]
    )

    minute = (

        fixture["fixture"]
        ["status"]
        ["elapsed"]

    ) or 0

    goals = (

        fixture["goals"]["home"] +

        fixture["goals"]["away"]

    )

    # --------------------------------
    # STATS
    # --------------------------------

    stats_data = get_fixture_statistics(
        fixture_id
    )

    results = stats_data.get(
        "results",
        0
    )

    if results != 2:

        register_live_feed(

            fixture["league"]["id"],
            league_name,

            False

        )

        return

    register_live_feed(

        fixture["league"]["id"],
        league_name,

        True

    )

    stats = stats_data["response"]

    home_stats = stats[0]["statistics"]
    away_stats = stats[1]["statistics"]

    # --------------------------------
    # AGGREGATE
    # --------------------------------

    sog = (

        safe_int(
            get_stat(
                home_stats,
                "Shots on Goal"
            )
        )

        +

        safe_int(
            get_stat(
                away_stats,
                "Shots on Goal"
            )
        )

    )

    shots = (

        safe_int(
            get_stat(
                home_stats,
                "Total Shots"
            )
        )

        +

        safe_int(
            get_stat(
                away_stats,
                "Total Shots"
            )
        )

    )

    corners = (

        safe_int(
            get_stat(
                home_stats,
                "Corner Kicks"
            )
        )

        +

        safe_int(
            get_stat(
                away_stats,
                "Corner Kicks"
            )
        )

    )

    passes = (

        safe_int(
            get_stat(
                home_stats,
                "Total passes"
            )
        )

        +

        safe_int(
            get_stat(
                away_stats,
                "Total passes"
            )
        )

    )

    xg = (

        safe_int(
            get_stat(
                home_stats,
                "expected_goals"
            )
        )

        +

        safe_int(
            get_stat(
                away_stats,
                "expected_goals"
            )
        )

    )

    # --------------------------------
    # ODDS
    # --------------------------------

    odd_data = get_live_odds(
        fixture_id
    )

    odd = extract_over15_odds(
        odd_data
    )

    # --------------------------------
    # FEED QUALITY
    # --------------------------------

    feed = feed_quality(

        sog > 0,

        shots > 0,

        corners > 0,

        passes > 0,

        True,

        xg > 0,

        odd is not None

    )

    # --------------------------------
    # REPORT 60'
    # --------------------------------

    if (

        minute >= 60

        and

        fixture_id not in reported_60

    ):

        reported_60[
            fixture_id
        ] = True

        bot_send(

            f"📡 LIVE FEED STATUS\n\n"

            f"{home} - {away}\n\n"

            f"🕒 {minute}'\n\n"

            f"📡 Feed Quality {feed}%\n"

            f"📈 {feed_status(feed)}"

        )

    # --------------------------------
    # TRIGGER WINDOW
    # --------------------------------

    if minute < 60:
        return

    if minute > 85:
        return

    # --------------------------------
    # ODDS FILTER
    # --------------------------------

    if odd is None:
        return

    if odd > 3.20:
        return

    # --------------------------------
    # ANTI SPAM
    # --------------------------------

    if fixture_id in triggered_matches:
        return

    # --------------------------------
    # SCORE
    # --------------------------------

    momentum = calculate_momentum(

        sog,
        shots,
        corners

    )

    score = trigger_score(

        sog,
        shots,
        corners,

        passes,

        xg,

        momentum,

        odd

    )

    needed = required_score(
        minute
    )

    if score < needed:

        return

    # --------------------------------
    # ALERT
    # --------------------------------

    bot_send(

        f"⚡ OVER 1.5 ST\n\n"

        f"{home} - {away}\n"

        f"🕒 {minute}'\n"

        f"⚽ Goals {goals}\n\n"

        f"🎯 SOG {sog}\n"
        f"📈 Shots {shots}\n"
        f"🚩 Corners {corners}\n\n"

        f"🧠 Momentum {momentum}\n"
        f"📡 Feed {feed}%\n\n"

        f"💰 Odd {odd}\n\n"

        f"🔥 Trigger Score {score}"

    )

    # --------------------------------
    # SAVE
    # --------------------------------

    save_trigger(

        fixture_id,

        f"{home} - {away}",

        league_name,

        minute,

        sog,

        shots,

        corners,

        xg,

        momentum,

        score,

        goals,

        odd,

        feed,

        datetime.now().isoformat()

    )

    triggered_matches[
        fixture_id
    ] = True

# =========================================================
# LIVE SCAN
# =========================================================

def live_scan(

    selected_matches,

    bot_send

):

    live = api_call(

        "https://v3.football.api-sports.io/"
        "fixtures?live=all"

    )

    matches = live.get(
        "response",
        []
    )

    print(
        "[LIVE] FOUND",
        len(matches)
    )

    for fixture in matches:

        fixture_id = (
            fixture["fixture"]["id"]
        )

        if fixture_id not in selected_matches:
            continue

        process_match(

            fixture,

            bot_send,

            fixture["league"]["name"]

        )
