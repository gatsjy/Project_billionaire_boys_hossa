import os
import json
import time
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr

from backtest.strategy import apply_strategy_v1
from backtest.data_loader import get_kosdaq_list, get_theme_stocks, get_daily_data

PORTFOLIO_FILE = 'portfolio.json'
LOG_DIR = 'trading_logs'

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "initial_capital": 2000000,
        "cash": 2000000,
        "holdings": [],
        "trade_history": []
    }

def save_portfolio(pf):
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)

def generate_markdown_report(today, pf, daily_trades, new_buys, total_value):
    profit_amt = total_value - pf['initial_capital']
    profit_pct = (profit_amt / pf['initial_capital']) * 100
    
    md = f"# 📈 억만장자 보이즈 클럽: 일일 매매 일지\n\n"
    md += f"## 📅 일자: {today}\n"
    md += f"- **💰 초기 자본금:** {pf['initial_capital']:,} 원\n"
    md += f"- **💵 현재 현금:** {pf['cash']:,} 원\n"
    md += f"- **📊 총 평가 자산:** {int(total_value):,} 원\n"
    md += f"- **📈 누적 수익률:** {profit_pct:.2f}%\n\n"
    
    md += "## 🔄 당일 청산(매도) 내역\n"
    if daily_trades:
        md += "| 종목명 | 매수일 | 매도가 | 수익률 | 사유 |\n"
        md += "|---|---|---|---|---|\n"
        for t in daily_trades:
            md += f"| {t['name']} | {t['buy_date']} | {int(t['sell_price']):,}원 | {t['profit_pct']:.2f}% | {t['reason']} |\n"
    else:
        md += "오늘 매도된 종목이 없습니다.\n"
        
    md += "\n## 🛒 당일 신규 매수 내역\n"
    if new_buys:
        md += "| 종목명 | 매수가 | 수량 |\n"
        md += "|---|---|---|\n"
        for b in new_buys:
            md += f"| {b['name']} | {int(b['buy_price']):,}원 | {b['qty']}주 |\n"
    else:
        md += "오늘 신규 매수한 종목이 없습니다.\n"
        
    md += "\n## 💼 현재 보유 종목 (Holdings)\n"
    if pf['holdings']:
        md += "| 종목명 | 매수가 | 수량 |\n"
        md += "|---|---|---|\n"
        for h in pf['holdings']:
            md += f"| {h['name']} | {int(h['buy_price']):,}원 | {h['qty']}주 |\n"
    else:
        md += "보유 중인 주식이 없습니다.\n"
        
    return md

def run_daily_paper_trading():
    today = datetime.today().strftime('%Y-%m-%d')
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 가상 매매 엔진 가동 시작 (멀티 테마 감시)")
    
    pf = load_portfolio()
    
    # 전체 테마주 로드
    theme_stocks = get_theme_stocks()
    if theme_stocks.empty:
        print("테마주 리스트가 없어 실행을 중단합니다.")
        return
        
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=60)
    
    daily_trades = []
    new_buys = []
    
    # 1. 기존 보유 종목 청산 검사 (손절 -2%, 익절 +5%)
    surviving_holdings = []
    for h in pf['holdings']:
        code = h['code']
        df = get_daily_data(code, start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
        if df.empty:
            surviving_holdings.append(h)
            continue
            
        last_row = df.iloc[-1]
        today_high = last_row['High']
        today_low = last_row['Low']
        today_close = last_row['Close']
        
        buy_price = h['buy_price']
        qty = h['qty']
        
        buy_date_obj = datetime.strptime(h['buy_date'], '%Y-%m-%d')
        days_held = (end_dt - buy_date_obj).days
        
        sold = False
        sell_price = 0
        reason = ""
        
        if today_low <= buy_price * 0.99:
            sell_price = buy_price * 0.99
            reason = "손절 (-1%)"
            sold = True
        elif today_high >= buy_price * 1.15:
            sell_price = buy_price * 1.15
            reason = "익절 (+15%)"
            sold = True
        elif days_held >= 3:
            sell_price = today_close
            reason = "보유기간 3일 경과 (종가 청산)"
            sold = True
            
        if sold:
            profit_pct = (sell_price - buy_price) / buy_price * 100
            pf['cash'] += sell_price * qty
            trade_record = {
                "code": code,
                "name": h['name'],
                "buy_date": h['buy_date'],
                "sell_date": today,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "profit_pct": profit_pct,
                "reason": reason
            }
            daily_trades.append(trade_record)
            pf['trade_history'].append(trade_record)
        else:
            surviving_holdings.append(h)
            
    pf['holdings'] = surviving_holdings
    
    # 2. 시장 전체 방향성 (인버스 헷지) 최우선 감시
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 코스피 시장 헷지(Hedge) 시그널 점검 중...")
    try:
        from backtest.index_strategy import apply_inverse_strategy
        kospi_df = fdr.DataReader('KS11')
        if not kospi_df.empty and len(kospi_df) >= 60:
            kospi_df = apply_inverse_strategy(kospi_df)
            if kospi_df.iloc[-1]['Inverse_Buy_Signal']:
                print("🚨 코스피 폭락 징후 포착! KODEX 인버스 매수 우선 검토")
                if sum(h['name'] == 'KODEX 인버스' for h in pf['holdings']) == 0:
                    inverse_df = fdr.DataReader('114800')
                    if not inverse_df.empty:
                        inv_price = inverse_df.iloc[-1]['Close']
                        if pf['cash'] >= 500000:
                            qty = 500000 // int(inv_price)
                            if qty > 0:
                                pf['cash'] -= qty * int(inv_price)
                                record = {
                                    "code": "114800",
                                    "name": "KODEX 인버스",
                                    "buy_price": int(inv_price),
                                    "qty": qty,
                                    "buy_date": today
                                }
                                pf['holdings'].append(record)
                                new_buys.append(record)
                                # 인버스를 샀다면, 다른 개별주식은 오늘 매수하지 않음 (방어 모드)
                                theme_stocks = pd.DataFrame()
                                print("방어 모드 발동: 오늘 개별 테마주 신규 매수를 중단합니다.")
    except Exception as e:
        print(f"인버스 로직 에러: {e}")

    # 3. 신규 매수 조건 검색 (테마주 한정)
    bet_amount = 500000 
    
    if not theme_stocks.empty and pf['cash'] >= bet_amount:
        print(f"신규 매수 탐색 중... (잔여 가상현금: {pf['cash']:,}원)")
        for idx, row in theme_stocks.iterrows():
            if pf['cash'] < bet_amount:
                break
                
            code = row['Code']
            name = row['Name']
            
            if any(h['code'] == code for h in pf['holdings']):
                continue
                
            df = get_daily_data(code, start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))
            if df.empty or len(df) < 25:
                continue
                
            df = apply_strategy_v1(df)
            if df.empty:
                continue
                
            last_date = df.index[-1]
            if df.loc[last_date, 'Buy_Signal']:
                buy_price = df.loc[last_date, 'Open']
                if buy_price == 0: continue
                
                qty = int(bet_amount // buy_price)
                if qty == 0: continue
                
                total_cost = buy_price * qty
                
                pf['cash'] -= total_cost
                buy_record = {
                    "code": code,
                    "name": name,
                    "buy_date": today,
                    "buy_price": float(buy_price),
                    "qty": qty
                }
                pf['holdings'].append(buy_record)
                new_buys.append(buy_record)
                print(f"[{name}] 신규 매수: {buy_price}원 x {qty}주")
                
    # 3. 포트폴리오 저장
    save_portfolio(pf)
    
    # 4. 일지 생성 및 폴더에 저장
    holdings_value = sum([h['buy_price'] * h['qty'] for h in pf['holdings']])
    total_value = pf['cash'] + holdings_value
    
    md_content = generate_markdown_report(today, pf, daily_trades, new_buys, total_value)
    
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        
    log_filename = os.path.join(LOG_DIR, f"{today}_log.md")
    with open(log_filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print(f"가상 매매 종료. 오늘의 매매 일지가 생성되었습니다: {log_filename}")

if __name__ == "__main__":
    run_daily_paper_trading()
