import os
import json

PORTFOLIO_FILE = 'portfolio.json'

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

def log_false_signal(trade_record):
    """
    손절 또는 손실 마감된 헛방(False Positive) 매매 기록을 CSV로 누적 저장합니다.
    """
    import csv
    from datetime import datetime
    
    log_dir = os.path.join(os.path.dirname(__file__), 'trading_logs')
    os.makedirs(log_dir, exist_ok=True)
    csv_file = os.path.join(log_dir, 'false_signals.csv')
    
    file_exists = os.path.exists(csv_file)
    
    with open(csv_file, 'a', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            # Header
            writer.writerow([
                'Sell Date', 'Code', 'Name', 'Theme', 
                'Buy Time', 'Buy Price', 'Sell Price', 'Loss Pct', 'Reason',
                'Trading Value (100M KRW)'
            ])
            
        writer.writerow([
            trade_record.get('sell_date', datetime.today().strftime('%Y-%m-%d')),
            trade_record.get('code', ''),
            trade_record.get('name', ''),
            trade_record.get('theme', ''),
            trade_record.get('buy_time', ''),
            trade_record.get('buy_price', 0),
            trade_record.get('sell_price', 0),
            f"{trade_record.get('profit_pct', 0):.2f}%",
            trade_record.get('reason', ''),
            trade_record.get('trading_value_100m', 0)
        ])
