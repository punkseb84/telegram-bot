import telebot
import os
import requests
from flask import Flask, request

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "OK"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    data = request.get_json()

    print("RAW:", data)

    if not data:
        return '', 200

    message = data.get("message")

    if not message:
        print("NO MESSAGE")
        return '', 200

    chat_id = message["chat"]["id"]
    text = message.get("text")

    print("TEXT:", text)

    if text:
        bot.send_message(chat_id, f"RICEVUTO: {text}")

    return '', 200


if __name__ == "__main__":
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/{TOKEN}")

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
