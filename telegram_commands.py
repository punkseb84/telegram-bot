# =========================================================
# telegram_commands.py
# BOT TRADER PRO ELITE AI
# =========================================================

from database import (

    get_all_coverage,
    get_last_triggers,
    export_csv,
    db_stats

)

from football_api import (

    get_api_requests,
    cache_info

)

from performance_engine import (

    performance_report,
    odds_performance_report

)

from live_engine import (
    get_live_feed_report
)

# =========================================================
# COVERAGE
# =========================================================

def cmd_coverage():

    rows = get_all_coverage()

    if not rows:

        return "Nessun dato coverage"

    txt = "📡 COVERAGE REPORT\n\n"

    for row in rows[:20]:

        txt += (

            f"{row['league']}\n"

            f"Coverage: "
            f"{row['coverage']}%\n\n"

        )

    return txt

# =========================================================
# PERFORMANCE
# =========================================================

def cmd_performance():

    return performance_report()

# =========================================================
# ODDS PERFORMANCE
# =========================================================

def cmd_oddsperf():

    return odds_performance_report()

# =========================================================
# API
# =========================================================

def cmd_api():

    cache = cache_info()

    txt = (

        "🔌 API STATUS\n\n"

        f"Requests: "
        f"{get_api_requests()}\n\n"

        f"Stats Cache: "
        f"{cache['stats_cache']}\n"

        f"Odds Cache: "
        f"{cache['odds_cache']}\n"

        f"Team Cache: "
        f"{cache['team_cache']}"

    )

    return txt

# =========================================================
# DEBUG
# =========================================================

def cmd_debug():

    stats = db_stats()

    txt = (

        "🛠 DEBUG\n\n"

        f"Triggers: "
        f"{stats['triggers']}\n"

        f"Leagues: "
        f"{stats['leagues']}"

    )

    return txt

# =========================================================
# LASTSCAN
# =========================================================

def cmd_lastscan():

    rows = get_last_triggers()

    if not rows:

        return "Nessun trigger"

    txt = "📈 LAST TRIGGERS\n\n"

    for row in rows:

        txt += (

            f"{row[0]}\n"

            f"{row[1]}'\n"

            f"Score {row[2]}\n"

            f"Odd {row[3]}\n\n"

        )

    return txt

# =========================================================
# LIVECHECK
# =========================================================

def cmd_livecheck(selected_matches):

    if not selected_matches:

        return "Nessuna partita monitorata"

    txt = "📡 LIVE CHECK\n\n"

    for fixture_id, match_name in selected_matches.items():

        txt += (

            f"{match_name}\n"

            f"Fixture: {fixture_id}\n\n"

        )

    return txt

# =========================================================
# EXPORT CSV
# =========================================================

def cmd_exportcsv():

    return export_csv()
# =========================================================
# LIVE FEED
# =========================================================

def cmd_livefeed():

    return get_live_feed_report()
