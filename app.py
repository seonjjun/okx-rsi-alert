from flask import Flask, jsonify
import requests
import pandas as pd

app = Flask(__name__)

# 텔레그램 설정
BOT_TOKEN = '8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI'
CHAT_ID = '6499273028'

# RSI 계산 함수
def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 텔레그램 알림 함수
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

@app.route('/')
def analyze():
    try:
        # 캔들 데이터 가져오기
        url = "https://proud-silence-8c85.bvd012.workers.dev/?type=candles"
        res = requests.get(url)
        candles = res.json().get("data", [])

        # 데이터프레임 구성
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "vol_usdt", "vol_dup", "complete"])
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)

        # RSI 계산 및 거래량 스파이크 탐지
        df["RSI"] = calculate_rsi(df["close"], period=14)
        vol_mean = df["volume"].rolling(window=20).mean()
        df["volume_spike"] = df["volume"] > vol_mean * 1.5

        # 조건 평가
        last_rsi = df["RSI"].iloc[-1]
        last_spike = df["volume_spike"].iloc[-1]

        if last_rsi < 35 and last_spike:
            msg = "🟢 RSI 과매도 + 거래량 급등 → 정찰병 진입 가능성"
        elif last_rsi > 70 and last_spike:
            msg = "🔴 RSI 과열 + 거래량 급등 → 세력 털기 가능성"
        else:
            msg = f"⚪ 조건 미충족 | RSI: {last_rsi:.2f}, 거래량 스파이크: {last_spike}"

        send_telegram(msg)
        return jsonify({"status": "ok", "message": msg})

    except Exception as e:
        send_telegram(f"🚨 분석 중 오류 발생: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run()
