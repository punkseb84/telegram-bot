import telebot
import os
import time

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# INVIA SUBITO MESSAGGIO
bot.send_message(CHAT_ID, "✅ TEST OK - BOT FUNZIONA")

# Mantiene il bot vivo (ma non blocca subito)
while True:
    time.sleep(10)
