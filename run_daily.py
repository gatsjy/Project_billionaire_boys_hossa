import os
import time
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr
import requests

from backtest.strategy import apply_strategy_v1
from backtest.data_loader import get_kosdaq_list, get_daily_data

# 텔레그램 설정 (환경 변수 또는 여기에 직접 입력)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1001360628906")

def send_telegram_message(message):
    """텔레그램 봇으로 메시지를 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("✅ 텔레그램 메시지 전송 성공")
    except Exception as e:
        print(f"❌ 텔레그램 메시지 전송 실패: {e}")

def run_daily_scanner():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 일일 종목 스캐너 시작...")
    
    # 1. 코스닥 리스트 수집
    kosdaq_list = get_kosdaq_list()
    
    # 데이터 수집 기간 (최근 30일 데이터만 있으면 20일 이평선 계산 가능)
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=60) 
    
    buy_signals = []
    
    # 장이 열리기 전이나 장 시작 직후에 실행된다고 가정할 때,
    # '오늘'의 시가 데이터가 확실히 필요합니다.
    # 만약 장 시작(9:00) 직후라면 당일 시가가 수집됩니다.
    
    print(f"코스닥 전 종목({len(kosdaq_list)}개) 스캔 중... (시간이 다소 소요됩니다)")
    
    count = 0
    for idx, row in kosdaq_list.iterrows():
        code = row['Code']
        name = row['Name']
        
        try:
            df = get_daily_data(code, start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
            
            if df.empty or len(df) < 25:
                continue
                
            df = apply_strategy_v1(df)
            if df.empty:
                continue
                
            # 가장 최근 거래일(보통 오늘 또는 전일)에 매수 시그널이 발생했는지 확인
            last_date = df.index[-1]
            if df.loc[last_date, 'Buy_Signal']:
                buy_signals.append({
                    'Code': code,
                    'Name': name,
                    'Date': last_date.strftime('%Y-%m-%d'),
                    'Prev_Volume': int(df.loc[last_date, 'Prev_Volume']),
                    'Prev_Close': int(df.loc[last_date, 'Prev_Close']),
                    'Open': int(df.loc[last_date, 'Open'])
                })
                
        except Exception as e:
            continue
            
        count += 1
        if count % 100 == 0:
            print(f"... {count}/{len(kosdaq_list)} 개 종목 완료")
            
    print("스캔 완료!")
    
    # 결과 포맷팅 및 텔레그램 전송
    if not buy_signals:
        msg = f"🔔 *억만장자 보이즈 클럽 알리미*\n오늘({datetime.today().strftime('%Y-%m-%d')})은 조건에 맞는 급등 매수 시그널 종목이 없습니다."
        send_telegram_message(msg)
    else:
        msg = f"🚀 *억만장자 보이즈 클럽 - 오늘의 추천 종목* 🚀\n"
        msg += f"기준일: {datetime.today().strftime('%Y-%m-%d')}\n\n"
        
        for item in buy_signals:
            msg += f"*{item['Name']} ({item['Code']})*\n"
            msg += f"▪ 전일 종가: {item['Prev_Close']:,}원\n"
            msg += f"▪ 금일 시가: {item['Open']:,}원\n"
            msg += f"▪ 전일 거래량: {item['Prev_Volume']:,}주 (급등)\n\n"
            
        msg += "⚠️ *주의사항*: 본 알림은 알고리즘 테스트용이며, 실제 투자는 본인의 판단하에 신중히 진행하세요."
        send_telegram_message(msg)

if __name__ == "__main__":
    run_daily_scanner()
