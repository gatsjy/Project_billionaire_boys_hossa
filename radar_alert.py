import os
import sys
import json
from datetime import datetime
import FinanceDataReader as fdr

sys.stdout.reconfigure(encoding='utf-8')

from notifier.email_sender import send_radar_alert
from backtest.data_loader import get_theme_stocks
from backtest.strategy import apply_strategy_v1
from backtest.realistic import CostModel
from backtest.params import (
    VOLUME_SPIKE_MULT, THEME_TP, THEME_SL,
    INVERSE_CODE, INVERSE_TP, INVERSE_SL, FEAR_SCORE_ENTRY,
    POSITION_SIZE,
)
from portfolio_manager import load_portfolio, save_portfolio, portfolio_lock

HISTORY_FILE = 'alert_history.json'
COST = CostModel()

# ⚠️ 데이터 한계(정직 고지): fdr.DataReader(code)는 '일봉(EOD)'을 반환한다.
# 따라서 아래 '현재가'는 엄밀한 장중 실시간 틱이 아니라 당일 일봉 종가의 근사다.
# 진짜 1분 실시간 감시는 키움 OpenAPI 실시간 시세 연동(kiwoom/kiwoom.py) 후에 가능하다.
# 그전까지 이 봇은 'EOD 근사 기반 가상매매'로 취급해야 한다.


def load_alert_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if data.get("date") == datetime.today().strftime('%Y-%m-%d'):
                return data.get("alerts", [])
    return []


def save_alert_history(alerts):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump({"date": datetime.today().strftime('%Y-%m-%d'), "alerts": alerts},
                  f, indent=4)


def _buy(pf, code, name, price, today, alerted_today, new_alerts, tp, sl, extra_msg=""):
    """비용 반영 가상 매수 + 이메일. 성공 시 True."""
    if pf['cash'] < POSITION_SIZE or any(h['code'] == code for h in pf['holdings']):
        return False
    qty = int(POSITION_SIZE // price)
    if qty <= 0:
        return False
    pf['cash'] -= qty * price * (1 + COST.buy_fee + COST.slippage)  # 매수비용 반영
    buy_record = {
        "type": "buy", "code": code, "name": name,
        "buy_date": today, "buy_price": float(price), "qty": qty,
    }
    pf['holdings'].append(buy_record)
    pf['trade_history'].append(buy_record)
    subject = f"{name} 가상 매수 체결"
    msg = (f"*[가상 매수 체결]*\n종목: {name} ({code})\n체결가: {int(price):,}원\n수량: {qty}주\n"
           f"목표 익절가: {int(price*(1+tp)):,}원 ({tp*100:+.0f}%)\n"
           f"손절가: {int(price*(1+sl)):,}원 ({sl*100:+.0f}%)\n{extra_msg}")
    send_radar_alert(subject, msg)
    alerted_today.append(code)
    new_alerts.append(code)
    return True


def run_radar():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 타점 레이더 + 가상매매(전략·비용 정합) 스캔 시작...")
    today = datetime.today().strftime('%Y-%m-%d')

    with portfolio_lock():  # 데몬과 EOD 결산의 동시 접근으로부터 장부 보호
        alerted_today = load_alert_history()
        new_alerts = []
        pf = load_portfolio()

        # 0. 보유 종목 익절/손절 감시 (파라미터를 params.py 단일소스에서 사용)
        surviving = []
        for h in pf['holdings']:
            code, buy_price, qty = h['code'], h['buy_price'], h['qty']
            tp, sl = (INVERSE_TP, INVERSE_SL) if code == INVERSE_CODE else (THEME_TP, THEME_SL)
            try:
                df = fdr.DataReader(code)
                if df.empty:
                    surviving.append(h); continue
                curr = float(df.iloc[-1]['Close'])
                reason = None
                if curr >= buy_price * (1 + tp):
                    reason = f"익절 ({tp*100:+.0f}%)"
                elif curr <= buy_price * (1 + sl):
                    reason = f"손절 ({sl*100:+.0f}%)"

                if reason:
                    profit_pct = COST.net_return(buy_price, curr) * 100  # 비용 반영 실현손익
                    pf['cash'] += curr * qty * (1 - COST.sell_fee - COST.tax - COST.slippage)
                    pf['trade_history'].append({
                        "type": "sell", "code": code, "name": h['name'],
                        "buy_date": h['buy_date'], "sell_date": today,
                        "buy_price": buy_price, "sell_price": curr,
                        "profit_pct": profit_pct, "reason": reason,
                    })
                    send_radar_alert(
                        f"[{reason}] {h['name']} 가상 매도 체결",
                        f"*[가상 매도 체결]*\n종목: {h['name']} ({code})\n"
                        f"매수가: {int(buy_price):,}원\n매도가: {int(curr):,}원\n"
                        f"수익률(비용반영): {profit_pct:.2f}%\n사유: {reason}\n")
                    print(f"[{h['name']}] {reason} 매도 (비용반영 {profit_pct:.2f}%)")
                else:
                    surviving.append(h)
            except Exception as e:
                print(f"보유 종목 {code} 스캔 에러: {e}")
                surviving.append(h)
        pf['holdings'] = surviving

        # 1. 매크로 공포점수 기반 인버스 헷징
        try:
            from backtest.macro_indicators import get_macro_fear_score
            macro = get_macro_fear_score()
            print(f"  [공포점수] {macro['score']}/4 - {macro['recommendation']}")
            for d in macro['details']:
                print(f"    > {d}")
            # 재진입 차단은 alert_history(파일, cwd 의존)가 아니라 '장부' 기준으로 판정.
            # 2026-07-09 인버스가 당일 4회 회전매매(합산 손실)된 원인이 파일 기반 차단의 구멍이었다.
            # 같은 날 인버스를 이미 사거나 판 기록이 있으면 재진입 금지 → 당일 손절-재매수 루프 차단.
            inv_traded_today = any(
                t.get('code') == INVERSE_CODE and
                (t.get('buy_date') == today or t.get('sell_date') == today)
                for t in pf['trade_history']
            )
            if (macro['score'] >= FEAR_SCORE_ENTRY
                    and INVERSE_CODE not in alerted_today
                    and not inv_traded_today):
                inv = fdr.DataReader(INVERSE_CODE)
                if not inv.empty:
                    price = int(inv.iloc[-1]['Close'])
                    detail = "\n".join(f"  - {d}" for d in macro['details'])
                    _buy(pf, INVERSE_CODE, "KODEX 인버스", price, today,
                         alerted_today, new_alerts, INVERSE_TP, INVERSE_SL,
                         extra_msg=f"\n[공포점수 {macro['score']}/4]\n{detail}")
            elif inv_traded_today:
                print("  [인버스] 오늘 이미 매매 기록 있음 — 재진입 차단(회전매매 방지)")
        except Exception as e:
            print(f"매크로 인버스 스캔 에러: {e}")

        # 2. 테마주 진입 — ★ 백테스트와 동일한 apply_strategy_v1 시그널 사용
        #    (기존의 'curr_vol >= vol_ma20 (1배)' 무차별 매수 로직 폐기 → 3배+갭+추세)
        theme_stocks = get_theme_stocks()
        if not theme_stocks.empty:
            for _, row in theme_stocks.iterrows():
                code = str(row['Code']).zfill(6)
                name = row['Name']
                if code in alerted_today:
                    continue
                try:
                    df = fdr.DataReader(code)
                    sig = apply_strategy_v1(df)
                    if sig.empty or not bool(sig.iloc[-1]['Buy_Signal']):
                        continue  # 오늘 봉이 백테스트 매수조건(거래량 3배·갭·추세)을 충족해야만 진입
                    price = float(sig.iloc[-1]['Close'])
                    _buy(pf, code, name, price, today, alerted_today, new_alerts,
                         THEME_TP, THEME_SL,
                         extra_msg=f"테마: {row.get('Theme', '수주산업')} / 거래량 {VOLUME_SPIKE_MULT}배 돌파")
                except Exception as e:
                    print(f"{name} 스캔 에러: {e}")

        save_portfolio(pf)

    if new_alerts:
        save_alert_history(alerted_today)
        print(f"신규 가상 매수 {len(new_alerts)}건 처리 완료.")
    else:
        print("조건에 부합하는 타점이 없습니다.")


if __name__ == "__main__":
    run_radar()
