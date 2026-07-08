import pandas as pd
from datetime import datetime, timedelta
import itertools

from strategy import apply_strategy_v1
from data_loader import get_theme_stocks, get_daily_data

def run_grid_search(start_date, end_date):
    print(f"[{start_date} ~ {end_date}] 피지컬 AI 테마 파라미터 최적화 시작...")
    
    theme_stocks = get_theme_stocks('physical_ai.csv')
    if theme_stocks.empty:
        print("테마주 리스트가 없습니다.")
        return
        
    # 미리 13개 종목의 과거 데이터를 다 받아놓기 (속도 최적화)
    print("과거 주가 데이터 다운로드 중...")
    stock_data = {}
    for idx, row in theme_stocks.iterrows():
        code = row['Code']
        df = get_daily_data(code, start_date, end_date)
        if not df.empty and len(df) >= 25:
            # 전략 시그널을 미리 다 계산
            df = apply_strategy_v1(df)
            stock_data[code] = df
    
    print("데이터 다운로드 및 전략 연산 완료. 백테스트 시뮬레이션 돌입...")
    
    # 테스트할 파라미터 조합 (Grid)
    take_profits = [0.03, 0.05, 0.07, 0.10, 0.15] # 3%, 5%, 7%, 10%, 15%
    stop_losses = [-0.01, -0.02, -0.03, -0.05]    # -1%, -2%, -3%, -5%
    
    results = []
    
    total_combinations = len(take_profits) * len(stop_losses)
    current = 0
    
    for tp, sl in itertools.product(take_profits, stop_losses):
        current += 1
        trades = []
        
        for code, df in stock_data.items():
            buy_dates = df[df['Buy_Signal']].index
            
            for buy_date in buy_dates:
                buy_price = df.loc[buy_date, 'Open']
                if buy_price == 0: continue
                
                sell_price = 0
                sell_date = None
                profit_pct = 0
                
                # 최대 3일 보유
                future_df = df.loc[buy_date:].iloc[1:4] 
                
                sold = False
                for f_date, f_row in future_df.iterrows():
                    high = f_row['High']
                    low = f_row['Low']
                    
                    if low <= buy_price * (1 + sl): # 손절 터치
                        sell_price = buy_price * (1 + sl)
                        profit_pct = sl * 100
                        sold = True
                        break
                    elif high >= buy_price * (1 + tp): # 익절 터치
                        sell_price = buy_price * (1 + tp)
                        profit_pct = tp * 100
                        sold = True
                        break
                
                if not sold and not future_df.empty:
                    # 3일차 종가 청산
                    sell_price = future_df.iloc[-1]['Close']
                    profit_pct = (sell_price - buy_price) / buy_price * 100
                    
                if sell_price > 0:
                    trades.append(profit_pct)
                    
        # 조합별 결과 집계
        if not trades:
            continue
            
        trades_series = pd.Series(trades)
        win_trades = trades_series[trades_series > 0]
        loss_trades = trades_series[trades_series <= 0]
        
        win_rate = len(win_trades) / len(trades) * 100
        avg_profit = win_trades.mean() if not win_trades.empty else 0
        avg_loss = loss_trades.mean() if not loss_trades.empty else 0
        
        expected_value = (win_rate/100 * avg_profit) + ((1 - win_rate/100) * avg_loss)
        total_accumulated_return = trades_series.sum() # 복리가 아닌 단리 누적 합계 (간단한 지표)
        
        results.append({
            'TP_Pct': int(tp * 100),
            'SL_Pct': int(sl * 100),
            'Total_Trades': len(trades),
            'Win_Rate': round(win_rate, 2),
            'Avg_Profit': round(avg_profit, 2),
            'Avg_Loss': round(avg_loss, 2),
            'Expectancy': round(expected_value, 2),
            'Total_Return': round(total_accumulated_return, 2)
        })
        
    # 데이터프레임으로 변환하여 기댓값(Expectancy) 순으로 정렬
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by='Expectancy', ascending=False)
    
    print("\n" + "="*60)
    print("파라미터 최적화(Grid Search) 결과 (기댓값 높은 순)")
    print("="*60)
    print(results_df.head(10).to_string(index=False))
    print("="*60)
    
    # 결과를 마크다운 형식으로 파일 저장
    with open('optimization_results.md', 'w', encoding='utf-8') as f:
        f.write("# 📊 피지컬 AI 테마 파라미터 최적화 (Grid Search) 결과\n\n")
        f.write(f"- **백테스트 기간:** {start_date} ~ {end_date}\n")
        f.write(f"- **테스트 대상:** 피지컬 AI 핵심 13개 종목\n")
        f.write("- **최적화 목표:** 1회 매매당 평균 기대 수익률(Expectancy) 극대화\n\n")
        
        f.write("## 🏆 최상위 파라미터 조합 (Top 10)\n\n")
        f.write("| 익절 (TP) | 손절 (SL) | 총 매매수 | 승률(%) | 평균 익절(%) | 평균 손절(%) | **기댓값(%)** | 단순 누적수익(%) |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for idx, r in results_df.head(10).iterrows():
            f.write(f"| +{r['TP_Pct']}% | {r['SL_Pct']}% | {r['Total_Trades']}회 | {r['Win_Rate']}% | {r['Avg_Profit']}% | {r['Avg_Loss']}% | **{r['Expectancy']}%** | {r['Total_Return']}% |\n")
            
        # 1위 분석
        best = results_df.iloc[0]
        f.write(f"\n## 💡 결론 및 적용\n")
        f.write(f"가장 기댓값이 높은 **최적의 방망이 길이는 `익절 +{best['TP_Pct']}%, 손절 {best['SL_Pct']}%`** 입니다.\n")
        f.write(f"승률은 **{best['Win_Rate']}%** 이며, 한 번 매수할 때마다 평균적으로 **+{best['Expectancy']}%**의 수익을 기대할 수 있는 훌륭한 시스템입니다.\n")
        f.write("\n이 수치를 `trading_conditions.md` 및 봇에 반영하여 내일부터 실전 적용할 것을 권장합니다.")
        
    print("\n최적화 결과가 optimization_results.md 로 저장되었습니다.")

if __name__ == "__main__":
    # 과거 3년 데이터 (테마주 데이터는 기간이 길어야 폭발적 상승기를 포함)
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=365 * 3)
    run_grid_search(start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
