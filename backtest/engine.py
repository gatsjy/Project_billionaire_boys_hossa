import pandas as pd
from strategy import apply_strategy_v1
from data_loader import get_kosdaq_list, get_daily_data
from datetime import datetime, timedelta

from realistic import resolve_exit, bars_from_df, evaluate, DEFAULT_COST
from params import THEME_TP as TP, THEME_SL as SL, TIME_STOP_DAYS


def run_backtest(start_date, end_date, cost=DEFAULT_COST):
    print(f"[{start_date} ~ {end_date}] 백테스트 시작 (갭·비용 반영)...")

    kosdaq_list = get_kosdaq_list()
    test_stocks = kosdaq_list.head(100)

    trades = []
    for _, row in test_stocks.iterrows():
        code, name = row['Code'], row['Name']
        try:
            df = get_daily_data(code, start_date, end_date)
            if df.empty or len(df) < 25:
                continue
            df = apply_strategy_v1(df)
            if df.empty:
                continue

            for buy_date in df[df['Buy_Signal']].index:
                buy_price = df.loc[buy_date, 'Open']
                if buy_price == 0:
                    continue
                future = bars_from_df(df, buy_date, TIME_STOP_DAYS)
                # ★ 갭 체결 + 비용을 반영한 현실 청산
                r = resolve_exit(buy_price, future, TP, SL, cost)
                if r is None:
                    continue
                trades.append({
                    'Code': code,
                    'Name': name,
                    'Buy_Date': buy_date.strftime('%Y-%m-%d'),
                    'Buy_Price': buy_price,
                    'Sell_Price': round(r['exit_price'], 2),
                    'Gross_Pct': round(r['gross_pct'], 2),
                    'Net_Pct': round(r['net_pct'], 2),   # 비용반영
                    'Reason': r['reason'],
                })
        except Exception:
            continue

    if not trades:
        print("조건에 맞는 매매 내역이 없습니다.")
        return

    trades_df = pd.DataFrame(trades).sort_values(by='Buy_Date')
    m = evaluate(trades_df['Net_Pct'].tolist())   # 비용반영 리스크 지표

    print("\n" + "=" * 46)
    print("[ Backtest Result — 갭·비용 반영 (Top 100) ]")
    print("=" * 46)
    print(f"총 매매 횟수     : {m['trades']}회")
    print(f"승률(Win Rate)   : {m['win_rate']}%")
    print(f"평균 수익/손실   : +{m['avg_win']}% / {m['avg_loss']}%")
    print(f"기댓값(비용반영) : {m['expectancy']}% / 매매")
    print(f"복리 누적수익    : {m['total_return']}%")
    print(f"최대낙폭(MDD)    : {m['max_drawdown']}%")
    print(f"최대 연속손실    : {m['max_losing_streak']}회")
    print(f"Profit Factor    : {m['profit_factor']}")
    print("=" * 46)
    verdict = "양(+) 기대 — 실전 검토 가능" if m['expectancy'] > 0 else \
              "음(-) 기대 — 비용을 이기지 못함. 실전 금지"
    print(f"판정: {verdict}")
    print("\n최근 매매 내역 (Top 5):")
    print(trades_df.tail(5).to_string(index=False))

if __name__ == "__main__":
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=365)
    run_backtest(start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
