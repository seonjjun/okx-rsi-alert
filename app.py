import requests
import pandas as pd
import numpy as np

# === 설정 ===
bot_token = "8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI"
chat_id = "7541916016"  # 실제 숫자 입력

def send_telegram(message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

# === 데이터 불러오기 ===
url = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=15m&limit=100"
res = requests.get(url)
data = res.json()["data"]

df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume","volumeCcy","volumeCcyQuote","confirm"])
df = df.iloc[::-1]  # 시간순 정렬
df["close"] = df["close"].astype(float)
df["volume"] = df["volume"].astype(float)

# === RSI 계산 ===
delta = df["close"].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()
rs = avg_gain / avg_loss
df["RSI"] = 100 - (100 / (1 + rs))

# === StochRSI 계산 ===
min_rsi = df["RSI"].rolling(14).min()
max_rsi = df["RSI"].rolling(14).max()
df["StochRSI"] = (df["RSI"] - min_rsi) / (max_rsi - min_rsi)

# === 볼린저밴드 계산 ===
df["ma20"] = df["close"].rolling(20).mean()
df["stddev"] = df["close"].rolling(20).std()
df["upper"] = df["ma20"] + 2 * df["stddev"]

# === 거래량 스파이크 ===
df["vol_avg5"] = df["volume"].rolling(5).mean()
df["vol_spike"] = df["volume"] > df["vol_avg5"] * 1.3

# === OBV 계산 ===
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

# === 마지막 캔들 기준 조건 판단 ===
last = df.iloc[-1]
condition = {
    "RSI": round(last["RSI"], 2),
    "StochRSI": round(last["StochRSI"], 2),
    "볼밴상단돌파": last["close"] >= last["upper"],
    "거래량스파이크": bool(last["vol_spike"]),
    "OBV상승세": last["OBV"] > last["OBV_MA"]
}

# === 조건 체크 ===
if (last["RSI"] >= 75 and 
    last["StochRSI"] >= 0.95 and 
    condition["볼밴상단돌파"] and 
    condition["거래량스파이크"] and 
    condition["OBV상승세"]):
    
    msg = (
        "🚨 구조 반전 시그널 감지!\n\n"
        f"• RSI: {condition['RSI']}\n"
        f"• StochRSI: {round(last['StochRSI'], 2)}\n"
        f"• 볼밴 상단 돌파: ✅\n"
        f"• 거래량 스파이크: ✅\n"
        f"• OBV 상승세: ✅"
    )
    print(msg)
    send_telegram(msg)

else:
    msg = (
        f"⭕ 조건 미충족\n"
        f"• RSI: {condition['RSI']}\n"
        f"• StochRSI: {round(last['StochRSI'], 2)}\n"
        f"• 볼밴 돌파: {condition['볼밴상단돌파']}\n"
        f"• 거래량 스파이크: {condition['거래량스파이크']}\n"
        f"• OBV 상승세: {condition['OBV상승세']}"
    )
    print(msg)
    send_telegram(msg)
