# =========================================================
# main.py
# BOT TRADER PRO ELITE AI
# =========================================================

import time
import threading

import telebot
from telebot.types import BotCommand

from config import (
    BOT_TOKEN,
    CHAT_ID
)

from prematch_engine import (
    select_matches
)

from live_engine import (
    live_scan
)

from performance_engine import (
    nightly_update
)

from telegram_commands import (

    cmd_coverage,
    cmd_performance,
    cmd_oddsperf,

    cmd_api,
    cmd_debug,

    cmd_lastscan,

    cmd_livecheck,
    cmd_exportcsv

)

from database import cursor

# =========================================================
# TELEGRAM
# =========================================================

bot = telebot.TeleBot(BOT_TOKEN)

bot.set_my_commands([

    BotCommand("start", "Avvia il bot"),
    BotCommand("oggi", "Selezione partite"),
    BotCommand("today", "Selezione partite"),

    BotCommand("livecheck", "Controllo live"),
    BotCommand("coverage", "Coverage leghe"),

    BotCommand("performance", "Performance"),
    BotCommand("oddsperf", "Performance quote"),

    BotCommand("api", "API status"),
    BotCommand("debug", "Debug sistema"),

    BotCommand("lastscan", "Ultimi trigger"),
    BotCommand("exportcsv", "Esporta CSV"),

    BotCommand("id", "Mostra Chat ID")

])

# =========================================================
# GLOBALS
# =========================================================

selected_matches = {}

# =========================================================
# SEND MESSAGE
# =========================================================

def send_message(text):

    try:

        if not CHAT_ID:

            print(
                "[TELEGRAM] CHAT_ID MISSING"
            )
            return

        bot.send_message(
            int(CHAT_ID),
            text
        )

    except Exception as e:

        print(
            "[TELEGRAM]",
            e
        )

# =========================================================
# DAILY SELECTION
# =========================================================

def daily_selection():

    global selected_matches

    try:

        selected_matches.clear()

        matches = select_matches()

        txt = "📋 TODAY SELECTION\n\n"

        if not matches:

            txt += (
                "⚠ Nessuna partita trovata"
            )

            send_message(txt)

            return

        for score, match in matches:

            fixture_id = (
                match["fixture"]["id"]
            )

            home = (
                match["teams"]["home"]["name"]
            )

            away = (
                match["teams"]["away"]["name"]
            )

            name = f"{home} - {away}"

            selected_matches[
                fixture_id
            ] = name

            txt += (

                f"{name}\n"
                f"Score {score}\n\n"

            )

        send_message(txt)

        print(
            "[PREMATCH] SELECTED",
            len(selected_matches)
        )

    except Exception as e:

        print(
            "[PREMATCH ERROR]",
            e
        )

# =========================================================
# LIVE THREAD
# =========================================================

def live_worker():

    while True:

        try:

            live_scan(

                selected_matches,

                send_message

            )

        except Exception as e:

            print(
                "[LIVE]",
                e
            )

        time.sleep(30)

# =========================================================
# NIGHTLY THREAD
# =========================================================

def nightly_worker():

    while True:

        try:

            now = time.localtime()

            if (

                now.tm_hour == 3

                and

                now.tm_min < 5

            ):

                nightly_update(
                    cursor
                )

                time.sleep(360)

        except Exception as e:

            print(
                "[NIGHTLY]",
                e
            )

        time.sleep(60)

# =========================================================
# COMMANDS
# =========================================================

@bot.message_handler(commands=["start"])
def start_cmd(message):

    bot.reply_to(

        message,

        "BOT TRADER PRO ELITE AI ONLINE"

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["id"])
def id_cmd(message):

    bot.reply_to(

        message,

        f"Chat ID: {message.chat.id}"

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["oggi", "today"])
def today_cmd(message):

    daily_selection()

    bot.reply_to(

        message,

        "Selezione aggiornata"

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["coverage"])
def coverage_cmd(message):

    bot.reply_to(

        message,

        cmd_coverage()

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["performance"])
def performance_cmd(message):

    bot.reply_to(

        message,

        cmd_performance()

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["oddsperf"])
def oddsperf_cmd(message):

    bot.reply_to(

        message,

        cmd_oddsperf()

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["api"])
def api_cmd(message):

    bot.reply_to(

        message,

        cmd_api()

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["debug"])
def debug_cmd(message):

    bot.reply_to(

        message,

        cmd_debug()

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["lastscan"])
def lastscan_cmd(message):

    bot.reply_to(

        message,

        cmd_lastscan()

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["livecheck"])
def livecheck_cmd(message):

    bot.reply_to(

        message,

        cmd_livecheck(
            selected_matches
        )

    )

# ---------------------------------------------------------

@bot.message_handler(commands=["exportcsv"])
def exportcsv_cmd(message):

    try:

        file = cmd_exportcsv()

        with open(file, "rb") as f:

            bot.send_document(

                message.chat.id,

                f

            )

    except Exception as e:

        bot.reply_to(

            message,

            f"Errore export CSV: {e}"

        )

# =========================================================
# START THREADS
# =========================================================

threading.Thread(

    target=live_worker,

    daemon=True

).start()

threading.Thread(

    target=nightly_worker,

    daemon=True

).start()

# =========================================================
# AUTO SELECTION DAILY
# =========================================================

daily_selection()

# =========================================================
# POLLING RECOVERY
# =========================================================

while True:

    try:

        print(
            "[BOT] START POLLING"
        )

        bot.infinity_polling(

            timeout=60,

            long_polling_timeout=60

        )

    except Exception as e:

        print(
            "[POLLING]",
            e
        )

        time.sleep(15)
