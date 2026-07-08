import pandas as pd
import os
from datetime import datetime, timedelta

from strategy import apply_strategy_v1
from data_loader import get_daily_data
from realistic import resolve_exit, bars_from_df, evaluate, DEFAULT_COST

# ---------------------------------------------------------------------------
# 테마 가상매매 시뮬레이션 (2026-07 개편)
#   - realistic.resolve_exit 로 갭·비용 반영 (기존 정확체결 낙관편향 제거)
#   - 파라미터는 optimizer 의 '표본외 검증'을 통과한 값을 쓰는 것을 전제로 한다.
#     여기 기본값(+7/-3)은 예시일 뿐, optimizer 결과로 갱신할 것.
# ---------------------------------------------------------------------------

TP = 0.07
SL = -0.03
TIME_STOP_DAYS = 3


def run_simulation(theme_file, start_date, end_date, cost=DEFAULT_COST):
    print(f"[{theme_file}] 테마 백테스트 시뮬레이션 가동 중...")

    theme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'themes', theme_file)
    if not os.path.exists(theme_path):
        print(f"{theme_file} 테마 리스트가 없습니다.")
        return None

    theme_stocks = pd.read_csv(theme_path, dtype={'Code': str})
    theme_stocks['Code'] = theme_stocks['Code'].apply(lambda x: str(x).zfill(6))

    trades = []
    for _, row in theme_stocks.iterrows():
        code, name = row['Code'], row['Name']
        df = get_daily_data(code, start_date, end_date)
        if df.empty or len(df) < 25:
            continue
        df = apply_strategy_v1(df)

        for buy_date in df[df['Buy_Signal']].index:
            entry = df.loc[buy_date, 'Open']
            if entry == 0:
                continue
            future = bars_from_df(df, buy_date, TIME_STOP_DAYS)
            r = resolve_exit(entry, future, TP, SL, cost)
            if r is None:
                continue
            trades.append({
                "theme": theme_file.replace('.csv', ''),
                "name": name,
                "buy_date": buy_date.strftime('%Y-%m-%d'),
                "buy_price": int(entry),
                "sell_price": int(r['exit_price']),
                "gross_pct": round(r['gross_pct'], 2),
                "net_pct": round(r['net_pct'], 2),   # ★ 비용반영 실현수익률
                "reason": r['reason'],
            })
    return trades


if __name__ == "__main__":
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=365 * 3)

    themes = ['nuclear.csv', 'shipbuilding.csv', 'defense.csv']
    all_trades = []
    for t in themes:
        tr = run_simulation(t, start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
        if tr:
            all_trades.extend(tr)

    df_trades = pd.DataFrame(all_trades)
    if df_trades.empty:
        print("매매 내역이 없습니다.")
        raise SystemExit

    df_trades = df_trades.sort_values(by='buy_date')
    m = evaluate(df_trades['net_pct'].tolist())   # 비용반영 지표

    # 테마별(비용반영)
    theme_stats = []
    for theme in [t.replace('.csv', '') for t in themes]:
        t_df = df_trades[df_trades['theme'] == theme]
        if not t_df.empty:
            tm = evaluate(t_df['net_pct'].tolist())
            theme_stats.append(
                f"- **{theme.upper()}**: {tm['trades']}회, 승률 {tm['win_rate']}%, "
                f"복리누적 {tm['total_return']}%, MDD {tm['max_drawdown']}%")

    with open('../expected_profit_loss_log.md', 'w', encoding='utf-8') as f:
        f.write("# 📊 테마 가상매매 시뮬레이션 로그 (비용·갭 반영)\n\n")
        f.write(f"- **기준:** 과거 3년 실제 데이터 · 익절 +{TP*100:.0f}% / 손절 {SL*100:.0f}%\n")
        f.write(f"- **비용:** 왕복 약 {DEFAULT_COST.round_trip_drag()*100:.2f}% 반영 "
                "(수수료+거래세+슬리피지), 갭 체결 반영\n\n")
        f.write("## 🏆 종합 지표 (비용반영)\n")
        f.write(f"- **총 매매 횟수:** {m['trades']}회 (연 약 {int(m['trades']/3)}회)\n")
        f.write(f"- **승률:** {m['win_rate']}%\n")
        f.write(f"- **평균 수익 / 손실:** +{m['avg_win']}% / {m['avg_loss']}%\n")
        f.write(f"- **1회 기댓값(비용반영):** **{m['expectancy']}%**\n")
        f.write(f"- **복리 누적수익:** {m['total_return']}%\n")
        f.write(f"- **최대낙폭(MDD):** {m['max_drawdown']}%\n")
        f.write(f"- **최대 연속손실:** {m['max_losing_streak']}회\n")
        f.write(f"- **Profit Factor:** {m['profit_factor']}\n\n")
        f.write("## 🔥 테마별\n")
        for ts in theme_stats:
            f.write(ts + "\n")
        f.write("\n## 📝 최근 10건 (gross=체결수익, net=비용반영)\n")
        f.write("| 테마 | 종목 | 매수일 | 매도가 | gross | net | 사유 |\n|---|---|---|---|---|---|---|\n")
        for _, r in df_trades.sort_values(by='buy_date', ascending=False).head(10).iterrows():
            f.write(f"| {r['theme']} | {r['name']} | {r['buy_date']} | {r['sell_price']:,}원 | "
                    f"{r['gross_pct']:.2f}% | **{r['net_pct']:.2f}%** | {r['reason']} |\n")
        f.write("\n> 💡 **정직한 코멘트:** 이 수치는 갭 체결과 거래비용을 모두 반영한 값이다. "
                "기댓값이 양수이고 IS/OOS가 비슷할 때만 실전을 검토한다. "
                "MDD와 연속손실은 '실제로 견뎌야 하는 고통'이며 파라미터 채택의 필수 판단 기준이다.\n")

    print("시뮬레이션 완료. expected_profit_loss_log.md 생성됨.")
    print(f"  기댓값(비용반영) {m['expectancy']}%/매매 | 복리누적 {m['total_return']}% | "
          f"MDD {m['max_drawdown']}% | PF {m['profit_factor']}")
