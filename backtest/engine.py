import pandas as pd
from strategy import apply_strategy_v1
from data_loader import get_kosdaq_list, get_daily_data
from datetime import datetime, timedelta
import sys

def run_backtest(start_date, end_date):
    print(f"[{start_date} ~ {end_date}] 백테스트 시작...")
    
    # 1. 코스닥 리스트 수집
    kosdaq_list = get_kosdaq_list()
    # 시간 관계상 시가총액 상위 일부나 랜덤이 아닌, 상위 100개 종목 대상으로 우선 테스트
    test_stocks = kosdaq_list.head(100)
    
    trades = []
    
    for idx, row in test_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        
        try:
            df = get_daily_data(code, start_date, end_date)
            if df.empty or len(df) < 25:
                continue
                
            df = apply_strategy_v1(df)
            if df.empty:
                continue
                
            # 매수 시그널 발생 일자 찾기
            buy_dates = df[df['Buy_Signal']].index
            
            for buy_date in buy_dates:
                # 당일 시가 매수 가정
                buy_price = df.loc[buy_date, 'Open']
                if buy_price == 0:
                    continue
                    
                # 매도 로직 (손절 -3%, 익절 +7%, 최대 3일 보유)
                sell_price = 0
                sell_date = None
                profit_pct = 0
                
                # 매수일 이후 3일치 데이터 확인
                future_df = df.loc[buy_date:].iloc[1:4] # 매수일 다음날부터 최대 3일
                
                sold = False
                for f_date, f_row in future_df.iterrows():
                    high = f_row['High']
                    low = f_row['Low']
                    
                    if low <= buy_price * 0.97: # 손절 터치
                        sell_price = buy_price * 0.97
                        sell_date = f_date
                        profit_pct = -3.0
                        sold = True
                        break
                    elif high >= buy_price * 1.07: # 익절 터치
                        sell_price = buy_price * 1.07
                        sell_date = f_date
                        profit_pct = 7.0
                        sold = True
                        break
                
                if not sold and not future_df.empty:
                    # 3일차 종가 청산
                    sell_date = future_df.index[-1]
                    sell_price = future_df.iloc[-1]['Close']
                    profit_pct = (sell_price - buy_price) / buy_price * 100
                    
                if sell_date is not None:
                    trades.append({
                        'Code': code,
                        'Name': name,
                        'Buy_Date': buy_date.strftime('%Y-%m-%d'),
                        'Buy_Price': buy_price,
                        'Sell_Date': sell_date.strftime('%Y-%m-%d'),
                        'Sell_Price': sell_price,
                        'Profit_Pct': round(profit_pct, 2)
                    })
        except Exception as e:
            # print(f"Error processing {name} ({code}): {e}")
            continue
            
    # 결과 분석
    if not trades:
        print("조건에 맞는 매매 내역이 없습니다.")
        return
        
    trades_df = pd.DataFrame(trades)
    
    win_trades = trades_df[trades_df['Profit_Pct'] > 0]
    loss_trades = trades_df[trades_df['Profit_Pct'] <= 0]
    
    win_rate = len(win_trades) / len(trades_df) * 100
    avg_profit = win_trades['Profit_Pct'].mean() if not win_trades.empty else 0
    avg_loss = loss_trades['Profit_Pct'].mean() if not loss_trades.empty else 0
    
    expected_value = (win_rate/100 * avg_profit) + ((1 - win_rate/100) * avg_loss)
    
    print("\n" + "="*40)
    print("🎯 백테스트 결과 요약 (Top 100 종목 대상)")
    print("="*40)
    print(f"총 매매 횟수: {len(trades_df)}회")
    print(f"승률 (Win Rate): {win_rate:.2f}%")
    print(f"평균 익절률: {avg_profit:.2f}%")
    print(f"평균 손절률: {avg_loss:.2f}%")
    print(f"기댓값 (Expected Value): {expected_value:.2f}% per trade")
    print("="*40)
    print("최근 매매 내역 (Top 5):")
    print(trades_df.tail(5).to_string(index=False))

if __name__ == "__main__":
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=365)
    run_backtest(start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
