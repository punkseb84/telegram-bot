import telebot

    elif text == "/profit":
        bot.reply_to(msg, f"📈 Profit: {round(bankroll - 100,2)}")

    elif text == "/roi":

        total = sum(
            b["stake"]
            for b in bets
            if b["resolved"]
        )

        roi = (
            ((bankroll - 100) / total) * 100
            if total > 0 else 0
        )

        bot.reply_to(msg, f"📊 ROI: {round(roi,2)}%")

    elif text == "/bets":

        if not bets:
            bot.reply_to(msg, "Nessuna")

        else:
            txt = "\n".join([
                f"{b['match']} - {b['type']}"
                for b in bets
            ])

            bot.reply_to(msg, txt)

    elif text == "/open":

        open_bets = [
            b for b in bets
            if not b["resolved"]
        ]

        if not open_bets:
            bot.reply_to(msg, "Nessuna aperta")

        else:
            txt = "\n".join([
                f"{b['match']} - {b['type']}"
                for b in open_bets
            ])

            bot.reply_to(msg, txt)

    elif text == "/oggi":
        selezione_pro()

    elif text == "/api":
        bot.reply_to(msg, f"📡 API calls: {api_requests}")

# =========================================
# START
# =========================================

print("🚀 BOT TRADER PRO AVVIATO")

threading.Thread(
    target=loop,
    daemon=True
).start()

bot.infinity_polling(skip_pending=True)
