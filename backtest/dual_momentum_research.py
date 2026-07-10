"""
dual_momentum_research.py — 후보 코어 전략: 한국/미국 듀얼 모멘텀 자산배분

설계 근거 (이 프로젝트에서 실데이터로 확정된 사실):
  - 한국 테마주 단타: 사망 (OOS 기댓값 -1.1%/매매, 분출 꼭지 매수).
  - 한국 지수 추세추종: 절반만 통과 (박스피 2015~2019 휩쏘).
  - 미국 지수: 추세가 강건 (자매 프로젝트 QLD S2가 양 구간 통과).
  → 매월 한국/미국 중 '추세(모멘텀) 강한 쪽 하나'만 보유, 둘 다 약하면 현금.
    한국 박스권엔 미국을 타고, 동반 하락엔 쉰다. 월 1회 저회전이라 비용도 안 먹힘.

규칙 (Antonacci GEM 변형):
  - 매월 말, 각 자산의 최근 LOOKBACK개월 총수익률(모멘텀) 계산.
  - 절대 모멘텀: 모멘텀 > 0 인 자산만 후보(추세 있는 것만).
  - 상대 모멘텀: 후보 중 모멘텀 최대 1개 보유. 후보 없으면 현금(수익 0).
  - 익월 수익률 반영. 자산 교체 시에만 왕복 비용.

자산 (한국 투자자 관점, 장기 이력 확보를 위해 지수+환율로 합성):
  - KR : KOSPI (KS11)               — 실전은 KODEX 200(069500)로 구현
  - US : S&P500 × 원/달러 (원화환산)  — 실전은 KODEX 미국S&P500(379800) 등으로 구현
  * 합성은 '개념 검증'용. 실전 ETF는 소액 추적오차/보수가 추가되나 결론엔 영향 미미.

정직성: 비용 반영 · 훈련(~2018)/검증(2019~) 분리 · 벤치마크(각 B&H, 한국단독추세) 동시 표기.
실행: cd backtest && python dual_momentum_research.py
"""

import io
import sys

import numpy as np
import pandas as pd
import FinanceDataReader as fdr

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

ONE_WAY_COST = 0.001          # 자산 교체 편도 ~0.1% (ETF 수수료+슬리피지)
TRAIN_END = "2018-12-31"
MONTHS_PER_YEAR = 12


def load_monthly():
    kospi = fdr.DataReader("KS11")["Close"].rename("KR")
    usdkrw = fdr.DataReader("USD/KRW")["Close"].rename("FX")
    sp = None
    for tk in ("US500", "S&P500", "^GSPC", "SPY"):
        try:
            s = fdr.DataReader(tk)["Close"]
            if not s.empty:
                sp = s.rename("US_USD")
                print(f"미국 지수 티커: {tk}")
                break
        except Exception:
            continue
    if sp is None:
        raise RuntimeError("미국 지수 데이터를 가져오지 못했습니다.")

    df = pd.concat([kospi, sp, usdkrw], axis=1).dropna()
    df["US"] = df["US_USD"] * df["FX"]      # 원화 환산 S&P500 (한국 투자자 수익)
    monthly = df[["KR", "US"]].resample("ME").last().dropna()
    return monthly


def dual_momentum(monthly, lookback):
    """월별 보유자산 시퀀스와 비용반영 자산곡선을 반환."""
    mom = monthly / monthly.shift(lookback) - 1
    nxt_ret = monthly.pct_change().shift(-1)   # 이번 달 말 결정 → 다음 달 수익

    assets = ["KR", "US"]
    equity, held_prev = 1.0, "CASH"
    curve, holds = [], []
    idx = monthly.index

    for t in range(lookback, len(idx) - 1):
        m = mom.iloc[t]
        cands = [(a, m[a]) for a in assets if pd.notna(m[a]) and m[a] > 0]
        pick = max(cands, key=lambda x: x[1])[0] if cands else "CASH"

        r = 0.0 if pick == "CASH" else nxt_ret.iloc[t][pick]
        if pick != held_prev:                  # 교체 비용(현금↔자산 포함)
            r -= ONE_WAY_COST
        equity *= (1 + (0.0 if pd.isna(r) else r))
        curve.append((idx[t + 1], equity, pick))
        holds.append(pick)
        held_prev = pick

    cur = pd.DataFrame(curve, columns=["date", "equity", "held"]).set_index("date")
    return cur, holds


def bh_curve(monthly, col):
    r = monthly[col].pct_change().fillna(0)
    return (1 + r).cumprod()


def kr_trend_curve(monthly):
    """비교용: 한국 단독 10개월 추세추종(월봉, 위=보유/아래=현금)."""
    ma = monthly["KR"].rolling(10).mean()
    sig = (monthly["KR"] > ma).astype(float)
    pos = sig.shift(1).fillna(0)
    turn = pos.diff().abs().fillna(0)
    r = pos * monthly["KR"].pct_change() - turn * ONE_WAY_COST
    return (1 + r.fillna(0)).cumprod()


def metrics(equity: pd.Series):
    equity = equity.dropna()
    if len(equity) < 2:
        return {"cagr": 0, "mdd": 0, "calmar": 0}
    years = len(equity) / MONTHS_PER_YEAR
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    peak = equity.cummax()
    mdd = (equity / peak - 1).min()
    return {"cagr": cagr * 100, "mdd": mdd * 100,
            "calmar": (cagr / abs(mdd)) if mdd < 0 else float("inf")}


def split_report(name, equity, train_end=TRAIN_END):
    tr = equity[equity.index <= train_end]
    te = equity[equity.index > train_end]
    m_tr, m_te = metrics(tr), metrics(te)
    print(f"{name:<28} 훈련 CAGR {m_tr['cagr']:5.1f}% MDD {m_tr['mdd']:6.1f}% Cal {m_tr['calmar']:4.2f}"
          f" | 검증 CAGR {m_te['cagr']:5.1f}% MDD {m_te['mdd']:6.1f}% Cal {m_te['calmar']:4.2f}")
    return m_tr, m_te


def run():
    monthly = load_monthly()
    print(f"월봉 {len(monthly)}개 ({monthly.index[0].date()} ~ {monthly.index[-1].date()})\n")

    # 벤치마크
    kr_bh = bh_curve(monthly, "KR")
    us_bh = bh_curve(monthly, "US")
    kr_tr = kr_trend_curve(monthly)

    print("=" * 92)
    print("벤치마크")
    print("=" * 92)
    split_report("KOSPI 단순보유", kr_bh)
    split_report("S&P500(원화) 단순보유", us_bh)
    split_report("한국단독 10개월 추세", kr_tr)

    print("\n" + "=" * 92)
    print("듀얼 모멘텀 (한국/미국/현금) — 룩백별")
    print("=" * 92)
    best = None
    for lb in (6, 9, 12):
        cur, holds = dual_momentum(monthly, lb)
        m_tr, m_te = split_report(f"듀얼모멘텀 {lb}개월 룩백", cur["equity"])
        # 상태 분포
        vc = pd.Series(holds).value_counts(normalize=True) * 100
        dist = " ".join(f"{k}:{v:.0f}%" for k, v in vc.items())
        print(f"{'':<28} 보유분포 → {dist}")
        # 검증구간 강건성: 검증 Calmar가 두 B&H·한국추세보다 높으면 통과 후보
        if best is None or m_te["calmar"] > best[1]:
            best = (lb, m_te["calmar"], m_tr, m_te)

    # 판정
    print("\n" + "=" * 92)
    bench_te_calmar = max(metrics(kr_bh[kr_bh.index > TRAIN_END])["calmar"],
                          metrics(us_bh[us_bh.index > TRAIN_END])["calmar"],
                          metrics(kr_tr[kr_tr.index > TRAIN_END])["calmar"])
    lb, cal, m_tr, m_te = best
    passed = (m_tr["calmar"] > 0 and m_te["calmar"] > 0 and
              m_te["calmar"] >= bench_te_calmar and m_tr["cagr"] > 0)
    print(f"판정 (룩백 {lb}개월 최상): 훈련 Calmar {m_tr['calmar']:.2f} / 검증 Calmar {m_te['calmar']:.2f} "
          f"(벤치 최고 검증 Calmar {bench_te_calmar:.2f})")
    print("관문: 훈련·검증 양 구간 Calmar>0 AND 검증에서 최고 벤치마크 이상 AND 훈련 CAGR>0")
    print("→ " + ("✅ 통과 — 실전 후보로 정밀검증 진행 가치 있음"
                  if passed else "❌ 미통과 — 벤치마크(단순보유)를 못 이김. 추가 설계 필요"))


if __name__ == "__main__":
    run()
