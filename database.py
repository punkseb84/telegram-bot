# =========================================================
# database.py
# BOT TRADER PRO ELITE AI
# =========================================================

import sqlite3
import csv
import os

# =========================================================
# DATABASE
# =========================================================

DB_NAME = "trader.db"

conn = sqlite3.connect(
    DB_NAME,
    check_same_thread=False
)

cursor = conn.cursor()

# =========================================================
# INIT
# =========================================================

def init_db():

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

        feed_quality REAL,

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

    live_odd,

    feed_quality,

    created_at

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

        feed_quality,

        created_at

    )

    VALUES (

        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?

    )

    """,

    (

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

        feed_quality,

        created_at

    )

    )

    conn.commit()

# =========================================================
# UPDATE RESULT
# =========================================================

def update_result(

    fixture_id,

    final_goals,

    goal_after_trigger,

    final_score

):

    cursor.execute("""

    UPDATE trigger_history

    SET

        final_goals = ?,

        goal_after_trigger = ?,

        final_score = ?,

        result_checked = 1

    WHERE fixture_id = ?

    AND result_checked = 0

    """,

    (

        final_goals,

        goal_after_trigger,

        final_score,

        fixture_id

    )

    )

    conn.commit()

# =========================================================
# COVERAGE UPDATE
# =========================================================

def update_coverage(

    league_id,
    league_name,

    stats_available

):

    cursor.execute("""

    INSERT OR IGNORE INTO league_coverage (

        league_id,
        league_name,

        matches_checked,
        stats_available

    )

    VALUES (

        ?, ?, 0, 0

    )

    """,

    (

        league_id,
        league_name

    )

    )

    cursor.execute("""

    UPDATE league_coverage

    SET matches_checked = matches_checked + 1

    WHERE league_id = ?

    """,

    (

        league_id,

    )

    )

    if stats_available:

        cursor.execute("""

        UPDATE league_coverage

        SET stats_available = stats_available + 1

        WHERE league_id = ?

        """,

        (

            league_id,

        )

        )

    conn.commit()

# =========================================================
# GET COVERAGE
# =========================================================

def get_coverage(league_id):

    cursor.execute("""

    SELECT

        matches_checked,

        stats_available

    FROM league_coverage

    WHERE league_id = ?

    """,

    (

        league_id,

    )

    )

    row = cursor.fetchone()

    if not row:

        return 0

    checked = row[0]
    available = row[1]

    if checked == 0:
        return 0

    return round(

        (available / checked) * 100,

        2

    )

# =========================================================
# GET ALL COVERAGE
# =========================================================

def get_all_coverage():

    cursor.execute("""

    SELECT

        league_name,

        matches_checked,

        stats_available

    FROM league_coverage

    ORDER BY stats_available DESC

    """)

    rows = cursor.fetchall()

    result = []

    for row in rows:

        checked = row[1]
        available = row[2]

        coverage = 0

        if checked:

            coverage = round(

                (available / checked) * 100,

                2

            )

        result.append({

            "league": row[0],

            "checked": checked,

            "available": available,

            "coverage": coverage

        })

    return result

# =========================================================
# PERFORMANCE
# =========================================================

def get_performance():

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

    hitrate = 0

    if total:

        hitrate = round(

            wins * 100 / total,

            2

        )

    return {

        "total": total,

        "wins": wins,

        "hitrate": hitrate

    }

# =========================================================
# ODDS PERFORMANCE
# =========================================================

def get_odds_performance():

    cursor.execute("""

    SELECT

        live_odd,

        goal_after_trigger

    FROM trigger_history

    WHERE result_checked = 1

    """)

    rows = cursor.fetchall()

    return rows

# =========================================================
# LAST TRIGGERS
# =========================================================

def get_last_triggers(limit=10):

    cursor.execute("""

    SELECT

        match_name,

        minute,

        trigger_score,

        live_odd,

        created_at

    FROM trigger_history

    ORDER BY id DESC

    LIMIT ?

    """,

    (

        limit,

    )

    )

    return cursor.fetchall()

# =========================================================
# EXPORT CSV
# =========================================================

def export_csv():

    filename = "trigger_history.csv"

    cursor.execute("""

    SELECT *

    FROM trigger_history

    """)

    rows = cursor.fetchall()

    columns = [

        d[0]
        for d in cursor.description

    ]

    with open(

        filename,

        "w",

        newline="",

        encoding="utf-8"

    ) as f:

        writer = csv.writer(f)

        writer.writerow(columns)

        writer.writerows(rows)

    return filename

# =========================================================
# STATS
# =========================================================

def db_stats():

    cursor.execute(

        "SELECT COUNT(*) FROM trigger_history"

    )

    triggers = cursor.fetchone()[0]

    cursor.execute(

        "SELECT COUNT(*) FROM league_coverage"

    )

    leagues = cursor.fetchone()[0]

    return {

        "triggers": triggers,

        "leagues": leagues

    }

# =========================================================
# INIT
# =========================================================

init_db()
