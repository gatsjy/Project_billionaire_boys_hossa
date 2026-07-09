import pandas as pd
from datetime import datetime, timedelta
import itertools

from strategy import apply_strategy_v1
from data_loader import get_theme_stocks, get_daily_data
from realistic import resolve_exit, bars_from_df, evaluate, DEFAULT_COST
from params import TIME_STOP_DAYS as _TS

# ---------------------------------------------------------------------------
# 과최적화 방지 개편 (2026-07)
#
# 기존 optimizer 의 "익절 +15% / 손절 -1%가 최적" 결론은 신뢰할 수 없었다.
#   (1) 갭을 무시한 낙관 체결로 손절을 항상 정확히 -1%로 기록  → -1% 손절이 마법처럼 안전
#   (2) 거래비용/세금 0 → 실제로는 음(-)인 기댓값이 양(+)으로 보임
#   (3) 20개 조합 중 '단리 합산' 최댓값 1칸을 그대로 채택 → 소수 +15% 꼬리 승리에 과최적합
#   (4) train/test 분리 없음 → 표본 내(in-sample) 성적을 실전 기대치로 오인
#
# 개편:
#   - realistic.resolve_exit 로 갭·비용 반영
#   - 매수시그널을 날짜순으로 정렬해 앞 70%(train) / 뒤 30%(test)로 분리(walk-forward)
#   - 랭킹은 '표본 외(OOS) 비용반영 기댓값' 기준. train 성적은 참고로만 표기
#   - MDD·연속손실·Profit Factor 를 함께 보고해 과최적 파라미터를 걸러냄
# ---------------------------------------------------------------------------

TIME_STOP_DAYS = _TS


def collect_signals(stock_data):
    """파라미터와 무관한 매수 시그널(코드/날짜/시가/향후봉)을 한 번만 추출."""
    signals = []
    for code, df in stock_data.items():
        for buy_date in df[df['Buy_Signal']].index:
            entry = df.loc[buy_date, 'Open']
            if entry == 0:
                continue
            future = bars_from_df(df, buy_date, TIME_STOP_DAYS)
            if not future:
                continue
            signals.append((buy_date, entry, future))
    # 날짜순 정렬(walk-forward 분리를 위해)
    signals.sort(key=lambda s: s[0])
    return signals


def eval_combo(signals, tp, sl, cost=DEFAULT_COST):
    """한 파라미터 조합을 train/test 로 나눠 평가."""
    if not signals:
        return None
    cutoff = int(len(signals) * 0.7)
    train_ret, test_ret = [], []
    for i, (buy_date, entry, future) in enumerate(signals):
        r = resolve_exit(entry, future, tp, sl, cost)
        if r is None:
            continue
        (train_ret if i < cutoff else test_ret).append(r['net_pct'])

    m_train = evaluate(train_ret)
    m_test = evaluate(test_ret)
    if m_test.get('trades', 0) == 0:
        return None
    return {
        'TP_Pct': round(tp * 100, 1),
        'SL_Pct': round(sl * 100, 1),
        'Trades_IS': m_train['trades'],
        'Exp_IS': m_train['expectancy'],          # 표본내 기댓값(참고)
        'Trades_OOS': m_test['trades'],
        'Exp_OOS': m_test['expectancy'],          # ★ 랭킹 기준: 표본외 기댓값
        'Win_OOS': m_test['win_rate'],
        'PF_OOS': m_test['profit_factor'],
        'MDD_OOS': m_test['max_drawdown'],
        'Streak_OOS': m_test['max_losing_streak'],
        'CumRet_OOS': m_test['total_return'],
    }


def run_grid_search(start_date, end_date):
    print(f"[{start_date} ~ {end_date}] 파라미터 최적화(walk-forward, 비용반영) 시작...")

    theme_stocks = get_theme_stocks()
    if theme_stocks.empty:
        print("테마주 리스트가 없습니다.")
        return

    print("과거 주가 데이터 다운로드 중...")
    stock_data = {}
    for _, row in theme_stocks.iterrows():
        code = row['Code']
        df = get_daily_data(code, start_date, end_date)
        if not df.empty and len(df) >= 25:
            stock_data[code] = apply_strategy_v1(df)

    signals = collect_signals(stock_data)
    print(f"데이터/시그널 준비 완료. 총 시그널 {len(signals)}건. 백테스트 돌입...")

    take_profits = [0.03, 0.05, 0.07, 0.10, 0.15]
    stop_losses = [-0.02, -0.03, -0.05, -0.07]   # -1%는 노이즈로 필히 터져 제외

    results = []
    for tp, sl in itertools.product(take_profits, stop_losses):
        r = eval_combo(signals, tp, sl)
        if r:
            results.append(r)

    if not results:
        print("유효한 결과가 없습니다.")
        return

    results_df = pd.DataFrame(results).sort_values(by='Exp_OOS', ascending=False)

    print("\n" + "=" * 78)
    print("파라미터 최적화 결과 — '표본외(OOS) 비용반영 기댓값' 순")
    print("=" * 78)
    print(results_df.to_string(index=False))
    print("=" * 78)

    best = results_df.iloc[0]
    verdict = "양(+) 기대 — 실전 검토 가능" if best['Exp_OOS'] > 0 else \
              "음(-) 기대 — 이 전략은 비용을 이기지 못함. 실전 금지"

    with open('optimization_results.md', 'w', encoding='utf-8') as f:
        f.write("# 📊 파라미터 최적화 결과 (Walk-Forward · 비용반영)\n\n")
        f.write(f"- **백테스트 기간:** {start_date} ~ {end_date}\n")
        f.write("- **방법:** 매수시그널 날짜순 앞 70% 학습(IS) / 뒤 30% 검증(OOS)\n")
        f.write("- **랭킹 기준:** 표본외(OOS) **비용·세금·슬리피지 반영** 1회 기댓값\n")
        f.write(f"- **왕복 비용 가정:** 약 {DEFAULT_COST.round_trip_drag()*100:.2f}% "
                "(수수료+거래세+슬리피지)\n\n")
        f.write("> ⚠️ 이전 버전의 '익절+15/손절-1이 최적'은 갭·비용을 무시한 낙관 체결의 산물이었다. "
                "아래 수치는 그 왜곡을 제거한 값이다.\n\n")
        f.write("| TP | SL | IS기댓값 | OOS기댓값 | OOS승률 | OOS PF | OOS MDD | 연속손실 | OOS누적 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for _, r in results_df.iterrows():
            f.write(f"| +{r['TP_Pct']}% | {r['SL_Pct']}% | {r['Exp_IS']}% | "
                    f"**{r['Exp_OOS']}%** | {r['Win_OOS']}% | {r['PF_OOS']} | "
                    f"{r['MDD_OOS']}% | {r['Streak_OOS']}회 | {r['CumRet_OOS']}% |\n")
        f.write(f"\n## 💡 결론\n")
        f.write(f"표본외 기준 최상위 조합: **익절 +{best['TP_Pct']}% / 손절 {best['SL_Pct']}%** — "
                f"OOS 기댓값 **{best['Exp_OOS']}%/매매**, PF {best['PF_OOS']}, MDD {best['MDD_OOS']}%.\n\n")
        f.write(f"**판정: {verdict}**\n\n")
        f.write("- IS기댓값 ≫ OOS기댓값 이면 과최적화 신호다. 두 값이 비슷하고 둘 다 양수여야 신뢰한다.\n")
        f.write("- PF < 1 또는 OOS기댓값 ≤ 0 인 조합은 비용을 이기지 못하므로 실전 투입 금지.\n")

    print(f"\n판정: {verdict}")
    print("최적화 결과가 optimization_results.md 로 저장되었습니다.")


if __name__ == "__main__":
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=365 * 3)
    run_grid_search(start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
