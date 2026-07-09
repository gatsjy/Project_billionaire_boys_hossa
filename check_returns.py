import FinanceDataReader as fdr
import json

with open('portfolio.json', 'r', encoding='utf-8') as f:
    pf = json.load(f)

val = pf['cash']
print(f"Cash: {val}")

for h in pf['holdings']:
    df = fdr.DataReader(h['code'])
    p = float(df.iloc[-1]['Close'])
    v = p * h['qty']
    val += v
    r = (p - h['buy_price']) / h['buy_price'] * 100
    print(f"{h['name']} ({h['code']}): {p}원 ({r:.2f}%) -> {v}원")

ret = (val - pf['initial_capital']) / pf['initial_capital'] * 100
print(f"\nTotal Asset: {val}원 ({ret:.2f}%)")
