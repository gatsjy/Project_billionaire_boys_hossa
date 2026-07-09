import os
from datetime import datetime, timedelta
import FinanceDataReader as fdr

from backtest.data_loader import get_daily_data
from backtest.realistic import CostModel
from backtest.params import TIME_STOP_DAYS
from portfolio_manager import (
    load_portfolio, save_portfolio, portfolio_lock, business_days_between,
)
from notifier.email_sender import send_radar_alert

LOG_DIR = 'trading_logs'
COST = CostModel()


def _current_price(code, fallback):
    """보유 평가용 최신 종가. 실패 시 fallback(매수가)."""
    try:
        df = fdr.DataReader(code)
        if not df.empty:
            return float(df.iloc[-1]['Close'])
    except Exception:
        pass
    return fallback


def generate_markdown_report(today, pf, daily_trades, holdings_marks, total_value):
    profit_amt = total_value - pf['initial_capital']
    profit_pct = profit_amt / pf['initial_capital'] * 100

    md = "# 📈 억만장자 보이즈 클럽: 일일 가상 매매 일지\n\n"
    md += f"## 📅 일자: {today}\n"
    md += f"- **💰 초기 자본금:** {pf['initial_capital']:,} 원\n"
    md += f"- **💵 현재 현금:** {int(pf['cash']):,} 원\n"
    md += f"- **📊 총 평가 자산(현재가 기준):** {int(total_value):,} 원\n"
    md += f"- **📈 누적 수익률:** {profit_pct:.2f}%\n\n"

    md += "## 🔄 당일 매매 내역\n"
    if daily_trades:
        md += "| 종목명 | 매수일 | 구분 | 단가 | 수익률(비용반영) | 사유 |\n|---|---|---|---|---|---|\n"
        for t in daily_trades:
            if t['type'] == 'sell':
                md += (f"| {t['name']} | {t['buy_date']} | **매도** | {int(t['sell_price']):,}원 | "
                       f"{t['profit_pct']:.2f}% | {t['reason']} |\n")
            else:
                md += f"| {t['name']} | {t['buy_date']} | **매수** | {int(t['buy_price']):,}원 | - | 시그널 포착 |\n"
    else:
        md += "오늘 발생한 매매 내역이 없습니다.\n"

    md += "\n## 💼 현재 보유 종목 (현재가·미실현손익)\n"
    if holdings_marks:
        md += "| 종목명 | 매수가 | 현재가 | 수량 | 미실현손익 |\n|---|---|---|---|---|\n"
        for m in holdings_marks:
            md += (f"| {m['name']} | {int(m['buy_price']):,}원 | {int(m['curr']):,}원 | "
                   f"{m['qty']}주 | {m['unreal_pct']:.2f}% |\n")
    else:
        md += "보유 중인 주식이 없습니다.\n"
    return md


def run_daily_eod_tasks():
    today = datetime.today().strftime('%Y-%m-%d')
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 장 마감 EOD 결산 시작")

    with portfolio_lock():  # 레이더 데몬과의 동시 접근 방지
        pf = load_portfolio()
        end_dt = datetime.today()
        start_dt = end_dt - timedelta(days=30)
        today_trades = []

        # 1. 타임스탑: '영업일' 기준 (기존 캘린더일 버그 수정)
        surviving = []
        for h in pf['holdings']:
            days_held = business_days_between(h['buy_date'], end_dt)
            if days_held >= TIME_STOP_DAYS:
                df = get_daily_data(h['code'], start_dt.strftime('%Y-%m-%d'),
                                    end_dt.strftime('%Y-%m-%d'))
                if df.empty:
                    surviving.append(h); continue
                close = float(df.iloc[-1]['Close'])
                profit_pct = COST.net_return(h['buy_price'], close) * 100  # 비용 반영
                pf['cash'] += close * h['qty'] * (1 - COST.sell_fee - COST.tax - COST.slippage)
                rec = {
                    "type": "sell", "code": h['code'], "name": h['name'],
                    "buy_date": h['buy_date'], "sell_date": today,
                    "buy_price": h['buy_price'], "sell_price": close,
                    "profit_pct": profit_pct,
                    "reason": f"보유 {TIME_STOP_DAYS}영업일 경과 (EOD 타임스탑)",
                }
                pf['trade_history'].append(rec)
                today_trades.append(rec)
                print(f"[{h['name']}] 타임스탑 청산 (종가 {int(close):,}원, {profit_pct:.2f}%)")
            else:
                surviving.append(h)
        pf['holdings'] = surviving

        # 2. 오늘 장중 발생 매매 취합
        for t in pf['trade_history']:
            if ((t.get('buy_date') == today and t.get('type') == 'buy') or
                    (t.get('sell_date') == today and t.get('type') == 'sell')):
                if t not in today_trades:
                    today_trades.append(t)

        # 3. 평가액 — ★ 현재가로 마킹(기존 '매수가로 평가' 버그 수정)
        holdings_value = 0.0
        holdings_marks = []
        for h in pf['holdings']:
            curr = _current_price(h['code'], h['buy_price'])
            holdings_value += curr * h['qty']
            holdings_marks.append({
                "name": h['name'], "buy_price": h['buy_price'], "curr": curr,
                "qty": h['qty'],
                "unreal_pct": (curr - h['buy_price']) / h['buy_price'] * 100,
            })
        total_value = pf['cash'] + holdings_value

        save_portfolio(pf)

    md = generate_markdown_report(today, pf, today_trades, holdings_marks, total_value)
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = os.path.join(LOG_DIR, f"{today}_log.md")
    with open(log_filename, 'w', encoding='utf-8') as f:
        f.write(md)
    send_radar_alert(f"[가상매매 일지] {today} 결산 리포트", md)
    print(f"EOD 결산 종료. 일지 생성/발송 완료: {log_filename}")


if __name__ == "__main__":
    run_daily_eod_tasks()
