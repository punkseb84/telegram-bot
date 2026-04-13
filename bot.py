{\rtf1\ansi\ansicpg1252\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import requests\
import time\
import telegram\
import os\
\
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")\
CHAT_ID = os.getenv("CHAT_ID")\
API_KEY = os.getenv("API_KEY")\
\
bot = telegram.Bot(token=TELEGRAM_TOKEN)\
\
def send_message(msg):\
    bot.send_message(chat_id=CHAT_ID, text=msg)\
\
def calcola_IA(tiri, in_porta, corner):\
    IA = 0\
    if tiri >= 10:\
        IA += 1\
    if in_porta >= 4:\
        IA += 1\
    if corner >= 5:\
        IA += 1\
    return IA\
\
def check_matches():\
    url = "https://v3.football.api-sports.io/fixtures?live=all"\
    headers = \{"x-apisports-key": API_KEY\}\
    res = requests.get(url, headers=headers).json()\
\
    for match in res["response"]:\
        minuto = match["fixture"]["status"]["elapsed"]\
        home = match["teams"]["home"]["name"]\
        away = match["teams"]["away"]["name"]\
        goals_home = match["goals"]["home"]\
        goals_away = match["goals"]["away"]\
\
        if minuto == 45 and goals_home == 0 and goals_away == 0:\
            try:\
                stats = match["statistics"][0]\
                tiri = stats["shots"]["total"]\
                in_porta = stats["shots"]["on"]\
                corner = stats["corners"]\
            except:\
                continue\
\
            IA = calcola_IA(tiri, in_porta, corner)\
\
            if IA >= 3:\
                segnale = "\uc0\u55357 \u57314  ENTRA ORA"\
            elif IA == 2:\
                segnale = "\uc0\u55357 \u57313  ENTRA RIDOTTO"\
            else:\
                segnale = "\uc0\u55357 \u56628  NON ENTRARE"\
\
            msg = f"""\uc0\u9917  \{home\} - \{away\}\
\uc0\u9201  0-0 HT\
\
Tiri: \{tiri\}\
In porta: \{in_porta\}\
Corner: \{corner\}\
\
\{segnale\}\
"""\
            send_message(msg)\
\
while True:\
    check_matches()\
    time.sleep(60)}