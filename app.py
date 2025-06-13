from flask import Flask, jsonify
import requests
import time
import hmac
import hashlib

app = Flask(__name__)

# OKX API 키 정보
API_KEY = 'ff8d0b4a-fdda-4de1-a579-b2076593b7fa'
SECRET_KEY = '49E886BC5608EAB889274AB16323A1B1'
PASSPHRASE = '#eseoAI0612'

# 텔레그램 봇 정보
BOT_TOKEN = '8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI'
CHAT_ID = '7541916016'  # 예: '123456789'

# 텔레그램 메시지 보내기 함수
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    res = requests.post(url, data=data)

    # 디버깅 로그 출력
    print(f"텔레그램 응답 상태코드: {res.status_code}")
    print(f"텔레그램 응답 내용: {res.text}")

# OKX REST API에서 캔들 데이터 요청
def get_kline_data(inst_id="BTC-USDT", bar="15m", limit=100):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": inst_id, "bar": bar, "limit": limit}
    response = requests.get(url, params=params)
    return response.json()

# RSI 계산 함수
def calculate_rsi(prices, period=14):
    deltas = [float(prices[i]) - float(prices[i-1]) for i in range(1, len(prices))]
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        gain = gains[i]
        loss = losses[i]

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

@app.route('/')
def index():
    try:
        kline_data = get_kline_data()
        close_prices = [item[4] for item in kline_data['data']][::-1]  # 종가 리스트 추출
        rsi = calculate_rsi(close_prices)

        # 조건: RSI가 70 이상이면 알림 전송
        if rsi >= 70:
            send_telegram(f"🔴 RSI 과매수! RSI: {rsi}")
        elif rsi <= 30:
            send_telegram(f"🟢 RSI 과매도! RSI: {rsi}")
        else:
            send_telegram(f"⚪ 조건 미충족 | RSI: {rsi}, 거래량 스파이크: False")

        return jsonify({"message": f"RSI: {rsi}", "status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run()
