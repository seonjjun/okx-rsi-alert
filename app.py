import requests
import pandas as pd
import numpy as np

# === 설정 ===
bot_token = "8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI"
chat_id = "7541916016"

# === 텔레그램 메시지 전송 ===
def send_telegram(message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

# === OHLCV 데이터 가져오기 ===
def fetch_candles(instId, timeframe):
    url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={timeframe}&limit=100"
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

# === 시나리오 분석 ===
def scenario_analysis(rsi_4h, obv_diff_4h, ema_position, volume_4h, avg_volume):
    if rsi_4h > 75 and obv_diff_4h > 0:
        return "과열 + 매집 정리 가능성 → 숏 시나리오 우세"
    elif rsi_4h < 40 and obv_diff_4h > 0:
        return "바닥 매집 감지 → 중장기 롱 가능성"
    elif not ema_position and obv_diff_4h < 0:
        return "지지 이탈 + 분산 조짐 → 구조 붕괴 시나리오"
    elif volume_4h < avg_volume:
        return "거래량 침체 → 추세 약화 / 정체 구간"
    else:
        return "애매한 구조 → 확실한 시그널 대기 필요"

# === 실행 ===
symbol = "VIRTUAL-USDT-SWAP"  # OKX 버추얼 심볼명

df_15m = calc_indicators(fetch_candles(symbol, "15m"))
df_1h = calc_indicators(fetch_candles(symbol, "1H"))
df_4h = calc_indicators(fetch_candles(symbol, "4H"))

last_15m = df_15m.iloc[-1]
last_1h = df_1h.iloc[-1]
last_4h = df_4h.iloc[-1]

signal_triggered = (
    last_15m["RSI"] >= 75 and
    last_15m["StochRSI"] >= 0.95 and
    last_15m["close"] >= last_15m["upper"] and
    last_15m["vol_spike"] and
    last_15m["OBV"] > last_15m["OBV_MA"]
)

scenario = scenario_analysis(
    last_4h["RSI"],
    last_4h["OBV"] - last_4h["OBV_MA"],
    last_4h["close"] >= df_4h["ma20"].iloc[-1],
    last_4h["volume"],
    df_4h["volume"].rolling(20).mean().iloc[-1]
)

if signal_triggered:
    msg = (
        "\n🚨 구조 반전 시그널 감지! (15분봉 기준)\n\n"
        f"[15분봉] RSI: {round(last_15m['RSI'],2)}, StochRSI: {round(last_15m['StochRSI'],2)}\n"
        f"볼밴 상단 돌파: ✅ | 거래량 스파이크: ✅ | OBV 상승세: ✅\n\n"
        f"[1시간봉] RSI: {round(last_1h['RSI'],2)} | OBV Δ: {round(last_1h['OBV'] - last_1h['OBV_MA'],2)}\n"
        f"[4시간봉] RSI: {round(last_4h['RSI'],2)} | OBV Δ: {round(last_4h['OBV'] - last_4h['OBV_MA'],2)}\n"
        f"시나리오: {scenario}"
    )
    send_telegram(msg)
    print("✅ 조건 충족 - 텔레그램 전송 완료")
else:
    print("⭕ 조건 미충족 - 텔레그램 전송 생략")
