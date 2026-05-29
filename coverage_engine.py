# =========================================================
# coverage_engine.py
# BOT TRADER PRO ELITE AI
# =========================================================

from database import (
    update_coverage,
    get_coverage
)

# =========================================================
# THRESHOLDS
# =========================================================

COVERAGE_BONUS = 80
COVERAGE_NEUTRAL = 60
COVERAGE_PENALTY = 30

# =========================================================
# REGISTER MATCH
# =========================================================

def register_live_feed(
    league_id,
    league_name,
    has_stats
):

    update_coverage(
        league_id,
        league_name,
        has_stats
    )

# =========================================================
# COVERAGE SCORE
# =========================================================

def coverage_modifier(league_id):

    coverage = get_coverage(
        league_id
    )

    # ----------------------------------
    # UNKNOWN
    # ----------------------------------

    if coverage == 0:

        return {

            "coverage": 0,

            "modifier": 0,

            "status": "UNKNOWN"

        }

    # ----------------------------------
    # BONUS
    # ----------------------------------

    if coverage >= COVERAGE_BONUS:

        return {

            "coverage": coverage,

            "modifier": 15,

            "status": "BONUS"

        }

    # ----------------------------------
    # NEUTRAL
    # ----------------------------------

    if coverage >= COVERAGE_NEUTRAL:

        return {

            "coverage": coverage,

            "modifier": 0,

            "status": "NEUTRAL"

        }

    # ----------------------------------
    # PENALTY
    # ----------------------------------

    if coverage >= COVERAGE_PENALTY:

        return {

            "coverage": coverage,

            "modifier": -20,

            "status": "PENALTY"

        }

    # ----------------------------------
    # EXCLUDED
    # ----------------------------------

    return {

        "coverage": coverage,

        "modifier": -999,

        "status": "EXCLUDED"

    }

# =========================================================
# LEAGUE ALLOWED
# =========================================================

def league_allowed(league_id):

    info = coverage_modifier(
        league_id
    )

    return (
        info["status"] != "EXCLUDED"
    )

# =========================================================
# PREMATCH BONUS
# =========================================================

def apply_coverage_bonus(
    league_id,
    current_score
):

    info = coverage_modifier(
        league_id
    )

    if info["status"] == "EXCLUDED":

        return None

    return (
        current_score +
        info["modifier"]
    )

# =========================================================
# COVERAGE TEXT
# =========================================================

def coverage_report_line(
    league_name,
    league_id
):

    info = coverage_modifier(
        league_id
    )

    return (

        f"{league_name}\n"

        f"Coverage: "
        f"{info['coverage']}%\n"

        f"Status: "
        f"{info['status']}"

    )

# =========================================================
# FEED QUALITY
# =========================================================

def feed_quality(

    has_sog,
    has_shots,
    has_corners,

    has_passes,
    has_possession,

    has_xg,
    has_odds

):

    score = 0

    if has_sog:
        score += 20

    if has_shots:
        score += 20

    if has_corners:
        score += 15

    if has_passes:
        score += 15

    if has_possession:
        score += 10

    if has_xg:
        score += 10

    if has_odds:
        score += 10

    return score

# =========================================================
# FEED STATUS
# =========================================================

def feed_status(feed_score):

    if feed_score >= 80:
        return "EXCELLENT"

    if feed_score >= 60:
        return "GOOD"

    if feed_score >= 40:
        return "LIMITED"

    return "POOR"
