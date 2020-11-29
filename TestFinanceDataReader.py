"""
  * @author Gatsjy
  * @since 2020-11-29
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""

import FinanceDataReader as fdr

#KOSDAQ = fdr.StockListing("KOSDAQ")["Symbol"]

datalist = {}

#for stock in KOSDAQ:
#    KOSDAQ_stock = fdr.DataReader(stock, '2020-11-27')['Close'][0]
#    datalist[stock] = KOSDAQ_stock

KOSDAQ_stock = fdr.DataReader('060310', '2020-11-27')

print(KOSDAQ_stock)