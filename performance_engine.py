# =========================================================
# performance_engine.py
# BOT TRADER PRO ELITE AI
# =========================================================

from football_api import api_call

from database import (

    update_result,

    get_performance,

    get_odds_performance

)

# =========================================================
# CHECK SINGLE FIXTURE
# =========================================================

def check_fixture_result(fixture_id):

    try:

        data = api_call(

            "https://v3.football.api-sports.io/"
            f"fixtures?id={fixture_id}"

        )

        response = data.get(
            "response",
            []
        )

        if not response:

            return None

        fixture = response[0]

        status = (

            fixture["fixture"]
            ["status"]
            ["short"]

        )

        # -------------------------
        # NOT FINISHED
        # -------------------------

        if status not in [

            "FT",
            "AET",
            "PEN"

        ]:

            return None

        home_goals = (
            fixture["goals"]["home"]
        ) or 0

        away_goals = (
            fixture["goals"]["away"]
        ) or 0

        total_goals = (
            home_goals +
            away_goals
        )

        final_score = (
            f"{home_goals}-{away_goals}"
        )

        return {

            "total_goals":
            total_goals,

            "final_score":
            final_score

        }

    except Exception as e:

        print(
            "[PERFORMANCE]",
            e
        )

        return None

# =========================================================
# PROCESS OPEN TRIGGERS
# =========================================================

def process_results(cursor):

    cursor.execute("""

    SELECT

        fixture_id,

        goals_at_trigger

    FROM trigger_history

    WHERE result_checked = 0

    """)

    rows = cursor.fetchall()

    print(

        "[PERFORMANCE] OPEN",

        len(rows)

    )

    for row in rows:

        fixture_id = row[0]

        goals_at_trigger = row[1]

        result = check_fixture_result(
            fixture_id
        )

        if result is None:

            continue

        final_goals = (
            result["total_goals"]
        )

        goal_after_trigger = 0

        if final_goals > goals_at_trigger:

            goal_after_trigger = 1

        update_result(

            fixture_id,

            final_goals,

            goal_after_trigger,

            result["final_score"]

        )

        print(

            "[PERFORMANCE] UPDATED",

            fixture_id,

            goal_after_trigger

        )

# =========================================================
# TELEGRAM PERFORMANCE
# =========================================================

def performance_report():

    perf = get_performance()

    return (

        "📊 PERFORMANCE\n\n"

        f"Trigger: "
        f"{perf['total']}\n"

        f"Hit: "
        f"{perf['wins']}\n"

        f"Hit Rate: "
        f"{perf['hitrate']}%"

    )

# =========================================================
# ODDS PERFORMANCE
# =========================================================

def odds_performance_report():

    rows = get_odds_performance()

    if not rows:

        return (
            "Nessun dato disponibile"
        )

    buckets = {

        "≤1.60": [0, 0],

        "1.61-2.00": [0, 0],

        "2.01-2.50": [0, 0],

        "2.51-3.20": [0, 0]

    }

    for odd, hit in rows:

        if odd is None:
            continue

        if odd <= 1.60:

            buckets["≤1.60"][0] += 1

            buckets["≤1.60"][1] += (
                hit or 0
            )

        elif odd <= 2.00:

            buckets["1.61-2.00"][0] += 1

            buckets["1.61-2.00"][1] += (
                hit or 0
            )

        elif odd <= 2.50:

            buckets["2.01-2.50"][0] += 1

            buckets["2.01-2.50"][1] += (
                hit or 0
            )

        else:

            buckets["2.51-3.20"][0] += 1

            buckets["2.51-3.20"][1] += (
                hit or 0
            )

    txt = "💰 ODDS PERFORMANCE\n\n"

    for label, values in buckets.items():

        total = values[0]
        wins = values[1]

        rate = 0

        if total:

            rate = round(

                wins * 100 / total,

                2

            )

        txt += (

            f"{label}\n"

            f"{wins}/{total}"

            f" ({rate}%)\n\n"

        )

    return txt

# =========================================================
# NIGHTLY JOB
# =========================================================

def nightly_update(cursor):

    print(
        "[PERFORMANCE] NIGHTLY START"
    )

    process_results(cursor)

    print(
        "[PERFORMANCE] NIGHTLY END"
    )
