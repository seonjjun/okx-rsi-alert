import requests
import pandas as pd
import numpy as np
import time
from flask import Flask, request

# === 설정 ===
bot_token = "8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI"
chat_id = 7541916016

app = Flask(__name__)

# === 텔레그램 메시지 전송 ===
def send_telegram(message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    print("📤 텔레그램 전송 내용:", message)
    response = requests.post(url, data=payload)
    print("📬 응답 상태:", response.status_code, response.text)


# === OHLCV 데이터 가져오기 ===
def fetch_candles(instId, timeframe):
    url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={timeframe}&limit=50"
    res = requests.get(url)
    data = res.json()["data"]
    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume","volumeCcy","volumeCcyQuote","confirm"])
    df = df.iloc[::-1]
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df

# === 인디케이터 계산 ===
def calc_indicators(df):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    min_rsi = df["RSI"].rolling(14).min()
    max_rsi = df["RSI"].rolling(14).max()
    df["StochRSI"] = (df["RSI"] - min_rsi) / (max_rsi - min_rsi)

    df["ma20"] = df["close"].rolling(20).mean()
    df["stddev"] = df["close"].rolling(20).std()
    df["upper"] = df["ma20"] + 2 * df["stddev"]

    df["vol_avg5"] = df["volume"].rolling(5).mean()
    df["vol_spike"] = df["volume"] > df["vol_avg5"] * 1.3

    obv = [0]
    for i in range(1, len(df)):
        if df["close"][i] > df["close"][i - 1]:
            obv.append(obv[-1] + df["volume"][i])
        elif df["close"][i] < df["close"][i - 1]:
            obv.append(obv[-1] - df["volume"][i])
        else:
            obv.append(obv[-1])
    df["OBV"] = obv
    df["OBV_MA"] = pd.Series(obv).rolling(14).mean()
    return df

# === 구조 분석 ===
def analyze_structure():
    df_15m = calc_indicators(fetch_candles("VIRTUAL-USDT-SWAP", "15m"))
    last = df_15m.iloc[-1]
    signal_triggered = (
        last["RSI"] >= 75 and
        last["StochRSI"] >= 0.95 and
        last["close"] >= last["upper"] and
        last["vol_spike"] and
        last["OBV"] > last["OBV_MA"]
    )
    if signal_triggered:
        msg = (
            f"🚨 구조 반전 시그널 감지!\n"
            f"RSI: {round(last['RSI'], 2)}\n"
            f"StochRSI: {round(last['StochRSI'], 2)}\n"
            f"볼밴 상단 돌파: ✅ | 거래량 스파이크: ✅ | OBV 상승세: ✅"
        )
    else:
        msg = (
            f"⭕ 조건 미충족\n"
            f"RSI: {round(last['RSI'], 2)}\n"
            f"StochRSI: {round(last['StochRSI'], 2)}\n"
            f"볼밴 돌파: {last['close'] >= last['upper']}\n"
            f"거래량 스파이크: {bool(last['vol_spike'])}\n"
            f"OBV 상승세: {last['OBV'] > last['OBV_MA']}"
        )
    send_telegram(msg)
    return msg

# === 시나리오 해석 ===
def scenario_analysis():
    df_4h = calc_indicators(fetch_candles("VIRTUAL-USDT-SWAP", "4H"))
    last = df_4h.iloc[-1]
    obv_diff = last["OBV"] - last["OBV_MA"]
    ema_support = last["close"] >= df_4h["ma20"].iloc[-1]
    volume_4h = last["volume"]
    avg_volume = df_4h["volume"].rolling(20).mean().iloc[-1]

    if last["RSI"] > 75 and obv_diff > 0:
        result = "과열 + 매집 정리 가능성 → 숏 시나리오 우세"
    elif last["RSI"] < 40 and obv_diff > 0:
        result = "바닥 매집 감지 → 중장기 롱 가능성"
    elif not ema_support and obv_diff < 0:
        result = "지지 이탈 + 분산 조짐 → 구조 붕괴 시나리오"
    elif volume_4h < avg_volume:
        result = "거래량 침체 → 추세 약화 / 정체 구간"
    else:
        result = "애매한 구조 → 확실한 시그널 대기 필요"

    msg = f"📈 [4H 시나리오 분석]\n{result}"
    send_telegram(msg)
    return msg

# === 커플링 분석 함수 ===
def check_coupling():
    df_virtual = fetch_candles("VIRTUAL-USDT-SWAP", "15m")
    df_btc = fetch_candles("BTC-USDT-SWAP", "15m")
    df_eth = fetch_candles("ETH-USDT-SWAP", "15m")
    corr_btc = df_virtual["close"].pct_change().corr(df_btc["close"].pct_change())
    corr_eth = df_virtual["close"].pct_change().corr(df_eth["close"].pct_change())
    msg = f"📊 커플링 지수\nBTC: {round(corr_btc, 2)}\nETH: {round(corr_eth, 2)}"
    send_telegram(msg)
    return msg

# === 텔레그램 웹훅 엔드포인트 ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("⚠️ 미분석 알림 도착\n데이터:", data)  # 👉 디버깅 로그 남기기

    message = data.get("message", {}).get("text", "")
    if "/커플링" in message:
        result = check_coupling()
    elif "/분석" in message:
        result = analyze_structure()
    elif "/시나리오" in message:
        result = scenario_analysis()
    else:
        result = "pong"

    return result  # ✅ 이 줄에서 상태코드를 따로 주지 말고 문자열만 리턴!


# === 앱 실행 ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
