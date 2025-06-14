import os
import pandas as pd
import requests
from flask import Flask, request
from ta.momentum import RSIIndicator

app = Flask(__name__)

# ✅ 성준의 텔레그램 정보
TELEGRAM_TOKEN = "8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI"
CHAT_ID = "7541916016"

# ✅ 텔레그램 메시지 전송 함수
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"❌ 텔레그램 전송 실패: {e}")

# ✅ OKX 캔들 데이터 요청 함수 (VIRTUAL, BTC, ETH)
def fetch_candles(symbol):
    url = f"https://proud-silence-8c85.bvd012.workers.dev?type=candles&symbol={symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        df = pd.DataFrame(data['data'], columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'volume2', 'quoteVolume', 'confirm'
        ])
        df['close'] = pd.to_numeric(df['close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
        return df.sort_values(by='timestamp')
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return pd.DataFrame()

# ✅ RSI 계산 함수
def calc_indicators(df):
    if df.empty:
        return None
    df = df.copy()
    df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
    return df

# ✅ 커플링 분석 함수
def check_coupling(df1, df2):
    if df1.empty or df2.empty:
        return "❌ 커플링 분석 실패: 데이터 부족"
    change1 = df1['close'].iloc[-1] - df1['close'].iloc[-2]
    change2 = df2['close'].iloc[-1] - df2['close'].iloc[-2]
    same_direction = (change1 * change2) > 0
    return "✅ 커플링 감지: 같은 방향" if same_direction else "⚠️ 커플링 없음"

# ✅ 웹훅 분석 엔드포인트
@app.route("/webhook", methods=['POST'])
def webhook():
    try:
        payload = request.get_json()
        if 'message' in payload and 'text' in payload['message']:
            text = payload['message']['text']
            if text.startswith("/분석"):
                virtual = fetch_candles("VIRTUAL-USDT")
                btc = fetch_candles("BTC-USDT")
                eth = fetch_candles("ETH-USDT")

                virtual = calc_indicators(virtual)
                if virtual is None:
                    send_telegram("❌ 구조 분석 실패: 데이터 수신 실패")
                    return 'ok'

                rsi = round(virtual['rsi'].iloc[-1], 2)
                msg = f"📊 [VIRTUAL] RSI: {rsi}\n"
                msg += check_coupling(virtual, btc) + " (BTC 기준)\n"
                msg += check_coupling(virtual, eth) + " (ETH 기준)"
                send_telegram(msg)
        return 'ok'
    except Exception as e:
        error_msg = f"🔥 분석 중 오류 발생: {e}"
        print(error_msg)
        send_telegram(error_msg)
        return 'error'
