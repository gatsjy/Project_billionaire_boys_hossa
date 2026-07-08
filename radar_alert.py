import os
import json
import pandas as pd
from datetime import datetime
import FinanceDataReader as fdr

from notifier.email_sender import send_radar_alert
from backtest.data_loader import get_theme_stocks

HISTORY_FILE = 'alert_history.json'

def load_alert_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 오늘 날짜의 알림 이력만 유지
            if data.get("date") == datetime.today().strftime('%Y-%m-%d'):
                return data.get("alerts", [])
    return []

def save_alert_history(alerts):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json_data = {
            "date": datetime.today().strftime('%Y-%m-%d'),
            "alerts": alerts
        }
        json.dump(json_data, f, indent=4)

def run_radar():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 1분 주기 타점 레이더 스캔 시작...")
    
    alerted_today = load_alert_history()
    new_alerts = []
    
    # 1. KODEX 인버스 타점 스캔 (930원 ~ 950원)
    try:
        inv_df = fdr.DataReader('114800')
        if not inv_df.empty:
            curr_inv_price = int(inv_df.iloc[-1]['Close'])
            if 930 <= curr_inv_price <= 950:
                if '114800' not in alerted_today:
                    subject = "코스피 하방 헷징 인버스 최적 타점 도달"
                    msg = (
                        "*[긴급 하방 헷징 타점 포착]*\n"
                        "코스피 데드캣 바운스 고점 도달 (인버스 매수 최적기)\n\n"
                        "종목: KODEX 인버스 (114800)\n"
                        f"현재가(매수가): {curr_inv_price:,}원\n"
                        f"목표 익절가: {int(curr_inv_price * 1.05):,}원 (+5%)\n"
                        f"손절가: {int(curr_inv_price * 0.98):,}원 (-2%)"
                    )
                    send_radar_alert(subject, msg)
                    alerted_today.append('114800')
                    new_alerts.append('114800')
    except Exception as e:
        print(f"인버스 스캔 에러: {e}")

    # 2. 테마주 슈팅 타점 스캔 (조선, 원전, 방산)
    theme_stocks = get_theme_stocks()
    if not theme_stocks.empty:
        for idx, row in theme_stocks.iterrows():
            code = str(row['Code']).zfill(6)
            name = row['Name']
            
            if code in alerted_today:
                continue
                
            try:
                df = fdr.DataReader(code)
                if len(df) < 21: continue
                
                # 어제까지의 20일 평균 거래량
                vol_ma20 = df['Volume'].iloc[-21:-1].mean()
                
                curr_vol = df['Volume'].iloc[-1]
                curr_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                
                # 로직: 장중 현재 거래량이 이미 20일 평균의 100%를 초과했고, 상승 중일 때 (슈팅 징후)
                if curr_vol >= vol_ma20 and curr_price > prev_price:
                    # 갭상승이 너무 크지 않은지 (4% 미만)
                    open_price = df['Open'].iloc[-1]
                    if open_price < prev_price * 1.04:
                        subject = f"{name} 단기 슈팅 타점 도달"
                        msg = (
                            f"*[테마 대장주 슈팅 타점 포착]*\n"
                            f"테마: {row.get('Theme', '수주산업')} / 장중 거래량 폭발\n\n"
                            f"종목: {name} ({code})\n"
                            f"현재가(매수가): {curr_price:,}원\n"
                            f"목표 익절가: {int(curr_price * 1.15):,}원 (+15%)\n"
                            f"손절가: {int(curr_price * 0.99):,}원 (-1%)"
                        )
                        send_radar_alert(subject, msg)
                        alerted_today.append(code)
                        new_alerts.append(code)
            except Exception as e:
                print(f"{name} 스캔 에러: {e}")
                
    if new_alerts:
        save_alert_history(alerted_today)
        print(f"새로운 알림 {len(new_alerts)}건 발송 완료.")
    else:
        print("조건에 부합하는 타점이 없습니다.")

if __name__ == "__main__":
    run_radar()
