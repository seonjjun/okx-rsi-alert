from flask import Flask, request
import requests
import pandas as pd
import json
import time
import ta
import telegram

app = Flask(__name__)

BOT_TOKEN = "8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI"
CHAT_ID = "7541916016"

# Cloudflare Workers 주소
WORKER_BASE = "https://proud-silence-8c85.bvd012.workers.dev"

def fetch_candles(symbol, interval="15m"):
    try:
        url = f"{WORKER_BASE}?type=candles&symbol={symbol}&bar={interval}"
        res = requests.get(url, timeout=10)
        raw = res.json()["data"]
        df = pd.DataFrame(raw, columns=[
            "timestamp", "open", "high", "low", "close", "vol", "_", "quote_vol", "__"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        df.set_index("timestamp", inplace=True)
        df = df.astype(float)
        return df
    except Exception as e:
        print("🔥 fetch_candles error:", e)
        return pd.DataFrame()

def calc_indicators(df):
    if df.empty:
        print("⚠️ calc_indicators: 빈 데이터프레임 받음")
        return df
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=6).rsi()
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(df["close"], df["vol"]).on_balance_volume()
    return df

def check_coupling(v_df, btc_df, eth_df):
    try:
        v_close = v_df["close"].iloc[-5:].pct_change().fillna(0)
        btc_close = btc_df["close"].iloc[-5:].pct_change().fillna(0)
        eth_close = eth_df["close"].iloc[-5:].pct_change().fillna(0)
        
        corr_btc = v_close.corr(btc_close)
        corr_eth = v_close.corr(eth_close)
        
        if corr_btc > corr_eth and corr_btc > 0.5:
            return f"🔗 BTC 커플링: {corr_btc:.2f}"
        elif corr_eth > 0.5:
            return f"🔗 ETH 커플링: {corr_eth:.2f}"
        else:
            return "❓ 커플링 없음 또는 낮은 상관관계"
    except Exception as e:
        return f"❌ 커플링 계산 오류: {e}"

def analyze_structure():
    v_df = calc_indicators(fetch_candles("VIRTUAL-USDT-SWAP"))
    btc_df = fetch_candles("BTC-USDT-SWAP")
    eth_df = fetch_candles("ETH-USDT-SWAP")

    if v_df.empty:
        return "❌ 구조 분석 실패: 데이터 수신 실패"
    
    latest = v_df.iloc[-1]
    msg = f"""📊 구조 분석 결과

💎 가격: {latest['close']:.4f}
📉 RSI(6): {latest['rsi']:.2f}
📈 OBV: {latest['obv']:,.0f}

{check_coupling(v_df, btc_df, eth_df)}
"""
    return msg

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    text = data.get("message", {}).get("text", "")
    if text == "/분석":
        msg = analyze_structure()
        bot = telegram.Bot(token=BOT_TOKEN)
        bot.send_message(chat_id=CHAT_ID, text=msg)
        return "ok"
    return "ignored"
