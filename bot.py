import telebot
import os

# Prende le variabili da Railway
TELEGRAM_TOKEN = os.getenv("8609230078:AAFCoriuwxzpAheNQMKZWZYbttR7aD_NUk")
CHAT_ID = os.getenv("168842957")

# Crea il bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Funzione invio messaggio
def send_message(msg):
    bot.send_message(CHAT_ID, msg)

# 🚀 TEST IMMEDIATO
send_message("✅ BOT ONLINE E COLLEGATO CORRETTAMENTE")

# Mantiene il bot attivo
while True:
    pass
