import os
import pandas as pd
import requests
from flask import Flask, request
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volume import OnBalanceVolumeIndicator
from telegram import Bot

app = Flask(__name__)

# ✅ 성준의 텔레그램 정보
TELEGRAM_TOKEN = "8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI"
CHAT_ID = "7541916016"
bot = Bot(token=TELEGRAM_TOKEN)

# ✅ OKX 캔들 데이터 요청 함수
def fetch_candles(symbol):
    url = f"https://proud-silence-8c85.bvd012.workers.dev?type=candles&symbol={symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        df = pd.DataFrame(data['data'], columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'volume2', 'quoteVolume', 'confirm']
        )
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
        return df.sort_values(by='timestamp')
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return pd.DataFrame()

# ✅ 보조지표 계산
def calc_indicators(df):
    if df.empty:
        return None
    df = df.copy()
    df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
    stoch = StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()
    df['obv'] = OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
    return df

# ✅ 커플링 판단 함수
def check_coupling(df1, df2):
    if df1.empty or df2.empty:
        return "❌ 커플링 분석 실패: 데이터 부족"
    change1 = df1['close'].iloc[-1] - df1['close'].iloc[-2]
    change2 = df2['close'].iloc[-1] - df2['close'].iloc[-2]
    same_direction = (change1 * change2) > 0
    return "✅ 커플링 감지: 같은 방향" if same_direction else "⚠️ 커플링 없음"

# ✅ /분석 명령 처리
@app.route("/webhook", methods=['POST'])
def webhook():
    try:
        payload = request.get_json()
        if 'message' in payload and 'text' in payload['message']:
            text = payload['message']['text']
            if text.startswith("/분석"):
                virtual = calc_indicators(fetch_candles("VIRTUAL-USDT"))
                if virtual is None:
                    bot.send_message(chat_id=CHAT_ID, text="❌ 구조 분석 실패: 데이터 수신 실패")
                    return 'ok'
                rsi = round(virtual['rsi'].iloc[-1], 2)
                stoch_k = round(virtual['stoch_k'].iloc[-1], 2)
                stoch_d = round(virtual['stoch_d'].iloc[-1], 2)
                obv = round(virtual['obv'].iloc[-1], 2)
                vol = round(virtual['volume'].iloc[-1], 2)
                msg = f"📊 [VIRTUAL 분석]\nRSI: {rsi}\nStoch %K: {stoch_k}, %D: {stoch_d}\nOBV: {obv}\n거래량: {vol}"
                bot.send_message(chat_id=CHAT_ID, text=msg)

            elif text.startswith("/커플링"):
                v = fetch_candles("VIRTUAL-USDT")
                b = fetch_candles("BTC-USDT")
                e = fetch_candles("ETH-USDT")
                msg = f"📡 커플링 분석 결과\n{check_coupling(v, b)} (BTC 기준)\n{check_coupling(v, e)} (ETH 기준)"
                bot.send_message(chat_id=CHAT_ID, text=msg)

            elif text.startswith("/롱"):
                v = calc_indicators(fetch_candles("VIRTUAL-USDT"))
                if v is None:
                    bot.send_message(chat_id=CHAT_ID, text="❌ 롱 분석 실패: 데이터 없음")
                    return 'ok'
                rsi = v['rsi'].iloc[-1]
                k = v['stoch_k'].iloc[-1]
                d = v['stoch_d'].iloc[-1]
                signal = "✅ 롱 진입 시그널" if rsi > 50 and k > d and k < 80 else "❌ 롱 진입 신호 약함"
                msg = f"📈 [롱 전략]\nRSI: {round(rsi,2)}, Stoch K: {round(k,2)}, D: {round(d,2)}\n→ {signal}"
                bot.send_message(chat_id=CHAT_ID, text=msg)

            elif text.startswith("/숏"):
                v = calc_indicators(fetch_candles("VIRTUAL-USDT"))
                if v is None:
                    bot.send_message(chat_id=CHAT_ID, text="❌ 숏 분석 실패: 데이터 없음")
                    return 'ok'
                rsi = v['rsi'].iloc[-1]
                k = v['stoch_k'].iloc[-1]
                d = v['stoch_d'].iloc[-1]
                signal = "✅ 숏 진입 시그널" if rsi < 50 and k < d and k > 20 else "❌ 숏 진입 신호 약함"
                msg = f"📉 [숏 전략]\nRSI: {round(rsi,2)}, Stoch K: {round(k,2)}, D: {round(d,2)}\n→ {signal}"
                bot.send_message(chat_id=CHAT_ID, text=msg)

            elif text.startswith("/시나리오"):
                msg = "🧠 시나리오 예시\n1. RSI 30이하 + Stoch 쌍바닥: 반등 시나리오\n2. RSI 70이상 + Stoch 역전: 하락 시나리오\n3. 거래량 급증 + OBV 상승: 매집 시나리오"
                bot.send_message(chat_id=CHAT_ID, text=msg)
        return 'ok'
    except Exception as e:
        print(f"🔥 분석 실패: {e}")
        return 'error'
