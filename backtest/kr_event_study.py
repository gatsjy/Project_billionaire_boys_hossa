"""
kr_event_study.py — '뉴스/이벤트 회피 필터'의 전제 검증 (2026-07)

배경: "뉴스를 크롤링해 고수익"이라는 아이디어를 정직하게 재정의하면, 뉴스의 유일한
검증가능 가치는 '매수 트리거'가 아니라 '이벤트(실적/공시) 구간 회피'(리스크 감소)다.
그 전제 — "한국 주식에서 실적 이벤트 구간이 실제로 위험해서 피할 가치가 있는가" — 를
미국 M7 연구(이벤트 변동성 8배·상회 41.8% 하락)와 동일한 방식으로 KOSPI 대형주에 검증한다.

결과 (KOSPI 18종목·870 실적 이벤트, yfinance):
  1. 이벤트 2일 반응 표준편차 3.31% vs 평상시 1일 2.62% → 약 1.3배.
     (무작위 2일 이동 ≈ 2.62%×√2 = 3.70%보다도 낮음!) → 대형주 '공식 실적일'은
     오히려 평상시보다 덜 출렁인다.
  2. 방향 예측 불가: 양(+)반응 46.8%, 갭상승 후 장중 53.8% 하락 (미국과 동일).
  3. 손실 꼬리 약함: 왜도 +0.20(급락 꼬리 없음), 최악 -17.8%는 예외적.

해석: 한국 대형주는 **잠정실적 공시**가 공식 실적일 수 주 전에 나와 서프라이즈를 선반영한다.
즉 진짜 변동성 이벤트는 '공식 실적일'이 아니라 '잠정실적 공시일'이라, yfinance 실적일 기반
회피 필터는 정작 위험한 날을 못 피한다. (소형 테마주의 공시 급등은 위험하나, 그건 이미
reversal_strategy 의 ATR 상한으로 처리하며 해당 전략 자체가 실전 부적합으로 판정됨.)

결론: 이 봇(지수 코어 + 은퇴한 개별주 전략)에 '실적 회피 필터'는 **구축 가치 없음**.
      추가 검증하려면 DART 개방 API 키로 '잠정실적/소형주 공시'일을 받아 재실험해야 한다.

실행: cd backtest && python kr_event_study.py   (yfinance .KS 실적일 사용)
"""
import io
import sys
import time

import numpy as np
import pandas as pd
import yfinance as yf

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", line_buffering=True)

KOSPI = {
    "삼성전자": "005930", "SK하이닉스": "000660", "카카오": "035720", "현대차": "005380",
    "LG화학": "051910", "삼성SDI": "006400", "셀트리온": "068270", "POSCO홀딩스": "005490",
    "현대모비스": "012330", "기아": "000270", "LG전자": "066570", "KB금융": "105560",
    "신한지주": "055550", "한국전력": "015760", "SK": "034730", "삼성생명": "032830",
    "SK텔레콤": "017670", "삼성전기": "009150",
}
RUNUP, DRIFT = 10, 3


def _earnings_retry(tk, retries=3):
    for a in range(retries):
        try:
            ed = tk.get_earnings_dates(limit=50)
            if ed is not None and not ed.empty:
                return ed
        except Exception:
            pass
        time.sleep(1.5 * (a + 1))
    return None


def run():
    rows = []
    for name, code in KOSPI.items():
        tkr = code + ".KS"
        px = yf.download(tkr, period="max", progress=False)
        if isinstance(px.columns, pd.MultiIndex):
            px.columns = px.columns.droplevel(1)
        px = px.dropna(subset=["Open", "Close"])
        if len(px) < 300:
            continue
        idx = px.index
        o, c = px["Open"].values, px["Close"].values
        base1 = np.nanstd(np.diff(c) / c[:-1])

        ed = _earnings_retry(yf.Ticker(tkr))
        if ed is None:
            print(f"  {name}: 실적일 조회 실패 — 건너뜀")
            continue
        ed = ed[ed.index < pd.Timestamp.now(tz=ed.index.tz)]
        for ts, _ in ed.iterrows():
            e = pd.Timestamp(ts.date())
            pos = idx.searchsorted(e)
            if pos >= len(idx):
                continue
            a = pos if idx[pos] == e else pos - 1
            if a - RUNUP < 0 or a + DRIFT + 1 >= len(idx):
                continue
            rows.append({
                "code": code,
                "runup": c[a - 1] / c[a - RUNUP] - 1,
                "reaction": c[a + 1] / c[a - 1] - 1,
                "gap": o[a + 1] / c[a] - 1,
                "intraday": c[a + 1] / o[a + 1] - 1,
                "base1": base1,
            })

    df = pd.DataFrame(rows)
    react, base = df["reaction"].values, df["base1"].mean()
    print(f"\n총 실적 이벤트 {len(df)}건 ({df['code'].nunique()}종목)\n")
    print("1. 이벤트 = 변동성 급증인가")
    print(f"   반응(2일) std {react.std()*100:.2f}% vs 평상시 1일 {base*100:.2f}% "
          f"(무작위 2일 ≈ {base*np.sqrt(2)*100:.2f}%) → {react.std()/base:.1f}배")
    print(f"   |반응|>5% {(np.abs(react)>0.05).mean()*100:.1f}% / >8% {(np.abs(react)>0.08).mean()*100:.1f}%")
    print("2. 방향 예측 가능한가")
    up = df[df["gap"] > 0]
    print(f"   평균반응 {react.mean()*100:+.2f}% 양(+) {(react>0).mean()*100:.1f}% | "
          f"갭업후 장중하락 {(up['intraday']<0).mean()*100:.1f}%")
    print("3. 손실 꼬리")
    print(f"   왜도 {pd.Series(react).skew():.2f} / 최악 {df['reaction'].min()*100:.1f}% / "
          f"corr(선반영,반응) {np.corrcoef(df['runup'], df['reaction'])[0,1]:+.3f}")
    print("\n판정: 대형주 공식 실적일은 평상시 수준 변동성(1.3배, 무작위 2일보다도 낮음) → "
          "회피 필터 가치 미미. 진짜 이벤트는 잠정실적 공시(DART) 쪽.")


if __name__ == "__main__":
    run()
