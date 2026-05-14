# =========================================================
# BOT TRADER PRO DEBUG LIVE
# VERSIONE CON DEBUG ENGINE COMPLETO
# =========================================================

import telebot
import os
import requests
import threading
import time

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

# =========================================================
# LEAGUES
# =========================================================

LEAGUES = [
    39,140,135,78,61,
    88,144,119,113,
    179,98,292,253,
    188,94,197,207
]

# =========================================================
# GLOBAL
# =========================================================

last_chat_id = None

selected_matches = {}

tracked_matches = {}

api_requests = 0

# =========================================================
# UTILS
# =========================================================

def log(*args):

    if DEBUG_MODE:
        print("[DEBUG]", *args)

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

def normalize(text):

    return text.split("@")[0].strip().lower()

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
# STATS
# =========================================================

def get_stat(stats, name):

    for s in stats:

        if s["type"] == name:
            return s["value"] or 0

    return 0

# =========================================================
# PREMATCH
# =========================================================

def selezione_pro():

    global selected_matches

    selected_matches.clear()

    today = datetime.now(tz).date()

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

            candidates.append(m)

        except:
            continue

    top = candidates[:3]

    msg = "🔥 PARTITE DEBUG\n\n"

    for m in top:

        fixture_id = m["fixture"]["id"]

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        selected_matches[fixture_id] = {

            "home": home,
            "away": away

        }

        msg += f"{home} - {away}\n"

    send(msg)

    log("SELECTED MATCHES", selected_matches)

# =========================================================
# LIVE DEBUG ENGINE
# =========================================================

def live_scan():

    data = api_call(

        "https://v3.football.api-sports.io/"
        "fixtures?live=all"

    )

    live_matches = data.get("response", [])

    log("LIVE MATCHES FOUND", len(live_matches))

    for m in live_matches:

        try:

            fixture_id = m["fixture"]["id"]

            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]

            match_name = f"{home} - {away}"

            # =============================================
            # CHECK IF TRACKED
            # =============================================

            if fixture_id not in selected_matches:

                log(
                    "SKIP NOT SELECTED",
                    match_name
                )

                continue

            log(
                "TRACKING MATCH",
                match_name
            )

            minute = (
                m["fixture"]["status"]["elapsed"]
            )

            home_goals = m["goals"]["home"]
            away_goals = m["goals"]["away"]

            total_goals = (
                home_goals + away_goals
            )

            log(
                "MATCH STATE",
                match_name,
                "MIN",
                minute,
                "GOALS",
                total_goals
            )

            # =============================================
            # STATS CHECK
            # =============================================

            stats = m.get("statistics")

            if not stats:

                log(
                    "NO STATS",
                    match_name
                )

                continue

            log(
                "STATS OK",
                match_name
            )

            try:

                hs = stats[0]["statistics"]
                as_ = stats[1]["statistics"]

            except Exception as e:

                log(
                    "STATS PARSE ERROR",
                    match_name,
                    e
                )

                continue

            # =============================================
            # XG
            # =============================================

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

            # =============================================
            # SHOTS
            # =============================================

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

            # =============================================
            # ATTACKS
            # =============================================

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

            # =============================================
            # CORNERS
            # =============================================

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

            # =============================================
            # DEBUG VALUES
            # =============================================

            log(

                "LIVE VALUES",

                match_name,

                "MIN", minute,

                "XG", xg,

                "SHOTS", shots,

                "ATTACKS", attacks,

                "MOMENTUM", momentum,

                "CORNERS", corners
            )

            # =============================================
            # TRIGGER CHECK
            # =============================================

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

                "RESULT",

                trigger
            )

            # =============================================
            # WHY NO TRIGGER
            # =============================================

            if not trigger:

                if minute < 60:
                    log("FAIL MINUTE")

                if total_goals > 1:
                    log("FAIL GOALS")

                if xg < 1.2:
                    log("FAIL XG")

                if momentum < 70:
                    log("FAIL MOMENTUM")

                if shots < 5:
                    log("FAIL SHOTS")

            # =============================================
            # SIGNAL
            # =============================================

            if trigger:

                if not tracked_matches.get(fixture_id):

                    tracked_matches[fixture_id] = True

                    log(
                        "TRIGGERED",
                        match_name
                    )

                    send(

                        f"⚡ DEBUG TRIGGER\n\n"
                        f"{match_name}\n"
                        f"🕒 {minute}'\n"
                        f"📈 xG {xg}\n"
                        f"🎯 Shots {shots}\n"
                        f"⚡ Momentum {momentum}"

                    )

        except Exception as e:

            log("LIVE ERROR", e)

# =========================================================
# LOOP
# =========================================================

def loop():

    while True:

        try:

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

    # =============================================
    # START
    # =============================================

    if text == "/start":

        bot.reply_to(

            msg,
            "🤖 DEBUG BOT ATTIVO"

        )

    # =============================================
    # OGGI
    # =============================================

    elif text == "/oggi":

        selezione_pro()

    # =============================================
    # API
    # =============================================

    elif text == "/api":

        bot.reply_to(

            msg,
            f"📡 API CALLS {api_requests}"

        )

    # =============================================
    # DEBUG
    # =============================================

    elif text == "/debug":

        txt = (

            "🧠 DEBUG STATUS\n\n"

            f"Tracked matches: "
            f"{len(selected_matches)}\n"

            f"Triggered: "
            f"{len(tracked_matches)}\n"

            f"API Calls: "
            f"{api_requests}\n"

            f"Debug mode: "
            f"{DEBUG_MODE}"

        )

        bot.reply_to(msg, txt)

# =========================================================
# START
# =========================================================

print(
    "🚀 BOT DEBUG LIVE AVVIATO"
)

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(
    skip_pending=True
)
