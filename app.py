import os
import pandas as pd
import requests
from flask import Flask, request
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volume import OnBalanceVolumeIndicator

app = Flask(__name__)

# ✅ 성준의 텔레그램 정보
TELEGRAM_TOKEN = "8170134694:AAF9WM10B9A9LvmfAPe26WoRse1oMUGwECI"
CHAT_ID = "7541916016"

# ✅ 텔레그램 메시지 전송 함수
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"❌ 텔레그램 전송 실패: {e}")

# ✅ 유사분석 API 호출 함수 (NaN 제거 포함)
def run_similarity_analysis(df):
    df = df.dropna()  # ✅ NaN 포함된 행 제거

    payload = {
        "close": df['close'].tolist(),
        "volume": df['volume'].tolist(),
        "rsi": df['rsi'].tolist(),
        "stoch": df['stoch_k'].tolist(),
        "obv": df['obv'].tolist()
    }
    try:
        res = requests.post("https://twoseo.onrender.com/analyze", json=payload)
        if res.status_code == 200:
            result = res.json()
            send_telegram_message(f"🧠 유사 분석 결과:\n{result}")
        else:
            send_telegram_message("❌ 유사분석 실패: 서버 오류")
    except Exception as e:
        send_telegram_message(f"❌ 유사분석 요청 실패: {e}")

# ✅ OKX 캔들 데이터 요청 함수 (봉 단위 추가)
def fetch_candles(symbol, interval="5m"):
    url = f"https://proud-silence-8c85.bvd012.workers.dev?type=candles&symbol={symbol}&interval={interval}"
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

            # ✅ 봉 선택 파싱 (기본 5m)
            interval = "5m"
            for keyword in ["1h", "4h", "15m", "5m"]:
                if keyword in text:
                    interval = keyword

            if text.startswith("/분석"):
                virtual = calc_indicators(fetch_candles("VIRTUAL-USDT", interval))
                if virtual is None:
                    send_telegram_message("❌ 구조 분석 실패: 데이터 수신 실패")
                    return 'ok'
                virtual = virtual.dropna()  # ✅ NaN 제거 추가
                rsi = round(virtual['rsi'].iloc[-1], 2)
                stoch_k = round(virtual['stoch_k'].iloc[-1], 2)
                stoch_d = round(virtual['stoch_d'].iloc[-1], 2)
                obv = round(virtual['obv'].iloc[-1], 2)
                vol = round(virtual['volume'].iloc[-1], 2)
                msg = f"📊 [VIRTUAL 분석 - {interval}봉]\nRSI: {rsi}\nStoch %K: {stoch_k}, %D: {stoch_d}\nOBV: {obv}\n거래량: {vol}"

                # 조건 분석
                conditions = []
                if rsi > 75:
                    conditions.append("🔥 RSI 과열 상태")
                if stoch_k < 20 and stoch_d < 20:
                    conditions.append("📉 Stoch 쌍바닥 가능성")
                if vol > virtual['volume'].iloc[-6:-1].mean() * 1.3:
                    conditions.append("💥 거래량 급증 포착")
                if obv > virtual['obv'].iloc[-2]:
                    conditions.append("🔼 OBV 상승 시작")

                if conditions:
                    msg += "\n\n🔍 조건 감지:\n" + "\n".join(conditions)
                    send_telegram_message(msg)
                    run_similarity_analysis(virtual)
                else:
                    msg += "\n\n😶 특이 조건 없음"
                    send_telegram_message(msg)

            elif text.startswith("/유사분석"):
                interval = "5m"
                for keyword in ["1h", "4h", "15m", "5m"]:
                    if keyword in text:
                        interval = keyword
                v = calc_indicators(fetch_candles("VIRTUAL-USDT", interval))
                if v is None:
                    send_telegram_message("❌ 유사분석 실패: 데이터 없음")
                    return 'ok'
                v = v.dropna()  # ✅ NaN 제거 추가
                send_telegram_message(f"📡 [유사분석 - {interval}봉] 실행 중...")
                run_similarity_analysis(v)

            elif text.startswith("/커플링"):
                v = fetch_candles("VIRTUAL-USDT", interval)
                b = fetch_candles("BTC-USDT", interval)
                e = fetch_candles("ETH-USDT", interval)
                msg = f"📡 커플링 분석 결과 ({interval}봉 기준)\n{check_coupling(v, b)} (BTC 기준)\n{check_coupling(v, e)} (ETH 기준)"
                send_telegram_message(msg)

            elif text.startswith("/롱"):
                v = calc_indicators(fetch_candles("VIRTUAL-USDT", interval))
                if v is None:
                    send_telegram_message("❌ 롱 분석 실패: 데이터 없음")
                    return 'ok'
                v = v.dropna()
                rsi = v['rsi'].iloc[-1]
                k = v['stoch_k'].iloc[-1]
                d = v['stoch_d'].iloc[-1]
                signal = "✅ 롱 진입 시그널" if rsi > 50 and k > d and k < 80 else "❌ 롱 진입 신호 약함"
                msg = f"📈 [롱 전략 - {interval}봉]\nRSI: {round(rsi,2)}, Stoch K: {round(k,2)}, D: {round(d,2)}\n→ {signal}"
                send_telegram_message(msg)

            elif text.startswith("/숏"):
                v = calc_indicators(fetch_candles("VIRTUAL-USDT", interval))
                if v is None:
                    send_telegram_message("❌ 숏 분석 실패: 데이터 없음")
                    return 'ok'
                v = v.dropna()
                rsi = v['rsi'].iloc[-1]
                k = v['stoch_k'].iloc[-1]
                d = v['stoch_d'].iloc[-1]
                signal = "✅ 숏 진입 시그널" if rsi < 50 and k < d and k > 20 else "❌ 숏 진입 신호 약함"
                msg = f"📉 [숏 전략 - {interval}봉]\nRSI: {round(rsi,2)}, Stoch K: {round(k,2)}, D: {round(d,2)}\n→ {signal}"
                send_telegram_message(msg)

            elif text.startswith("/시나리오"):
                msg = "🧠 시나리오 예시\n1. RSI 30이하 + Stoch 쌍바닥: 반등 시나리오\n2. RSI 70이상 + Stoch 역전: 하락 시나리오\n3. 거래량 급증 + OBV 상승: 매집 시나리오"
                send_telegram_message(msg)
        return 'ok'
    except Exception as e:
        print(f"🔥 분석 실패: {e}")
        return 'error'
