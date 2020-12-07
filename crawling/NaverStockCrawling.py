"""
  * @author Gatsjy
  * @since 2020-12-06
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
import random

class NaverStockCrawling():
    def __init__(self, news_crawling_result_data):
        # 크롤링 시작하자마자 돌리는 __init__
        print("***************************************************************************")
        print("************************** 네시버 증시 크롤링 시작 ****************************")
        print("***************************************************************************")

        print(news_crawling_result_data)

        # 다른 모듈과 의사소통할 전역 변수
        self.stock_info_list = {}

        # 2. 전 종목 뉴스 크롤링 중 언급 된 적 없는 리스트 추출
        stock_list = news_crawling_result_data

        ##############################test용 설정 ####################################
        # stock_list = stock_list[:10]['종목코드']
        #stock_list = stock_list[:100]['종목코드']
        stock_list = stock_list['종목코드']
        ##############################################################################

        yesterdaylastfirst = '20201207153000'
        yesterdaylastsecond = '2020120180000'

        ## * 참고 : [0] : 체결시각 [1] : 체결가 [2] : 전일비 [3] : 매도 [4] : 매수 [5] : 거래량 [6] : 변동량
        # 9시 되기 되기 전에 가져와야 할 것
        # 전날 15시 30분 00초 가격, 전날 15시 30분 00초 거래량, 전날 09시 01분 00초 거래량
        for stock in stock_list:
            yesterdaylastfirsturl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={yesterdaylastfirst}"
            raw = requests.get(yesterdaylastfirsturl, headers={'User-Agent': 'Mozilla/5.0'})
            yesterdaylastfirsthtml = BeautifulSoup(raw.text, "html.parser")
            yesterdaylastfirstPrices = yesterdaylastfirsthtml.select('body > table.type2 > tr:nth-child(3) > td > span')

            yesterdaylastsecondurl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={yesterdaylastsecond}"
            raw = requests.get(yesterdaylastsecondurl, headers={'User-Agent': 'Mozilla/5.0'})
            yesterdaylastsecondhtml = BeautifulSoup(raw.text, "html.parser")
            yesterdaylastsecondPrices = yesterdaylastsecondhtml.select('body > table.type2 > tr:nth-child(3) > td > span')

            stock_info = {}
            prevlastFirstTradesVolume = 0
            if len(yesterdaylastfirstPrices) > 5:
                prevlastFirstTradesVolume = int(yesterdaylastfirstPrices[5].text.replace(',', ''))

            prevlastSecondTradesVolume = 0
            if len(yesterdaylastsecondPrices) > 5:
                prevlastSecondTradesVolume = int(yesterdaylastsecondPrices[5].text.replace(',', ''))

            if prevlastSecondTradesVolume != 0 :
                plusTradesVolume = prevlastSecondTradesVolume-prevlastFirstTradesVolume

        print("***************************************************************************")
        print("************************** 네시버 증시 크롤링 끝 *****************************")
        print("***************************************************************************")