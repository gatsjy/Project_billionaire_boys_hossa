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

        #############################################
        ## 키움 api 시작하기 전에 네이버 크롤링을 통해 원하는 데이터를 가져와서 비교하는 로직 입니다
        #############################################

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

        yesterdaylast = '20201204153000'
        yesterdayfirst = '20201204090000'
        #yesterdayfirst = '20201203100000'  ## 수능날이여서 늦게 오픈

        ## * 참고 : [0] : 체결시각 [1] : 체결가 [2] : 전일비 [3] : 매도 [4] : 매수 [5] : 거래량 [6] : 변동량
        # 9시 되기 되기 전에 가져와야 할 것
        # 전날 15시 30분 00초 가격, 전날 15시 30분 00초 거래량, 전날 09시 01분 00초 거래량
        for stock in stock_list:
            yesterdaylasturl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={yesterdaylast}"
            raw = requests.get(yesterdaylasturl, headers={'User-Agent': 'Mozilla/5.0'})
            yesterdaylasthtml = BeautifulSoup(raw.text, "html.parser")
            yesterdaylastPrices = yesterdaylasthtml.select('body > table.type2 > tr:nth-child(3) > td > span')

            yesterdayfirsturl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={yesterdayfirst}"
            raw = requests.get(yesterdayfirsturl, headers={'User-Agent': 'Mozilla/5.0'})
            yesterdayfirsthtml = BeautifulSoup(raw.text, "html.parser")
            yesterdayfirstPrices = yesterdayfirsthtml.select('body > table.type2 > tr:nth-child(3) > td > span')

            stock_info = {}
            if len(yesterdaylastPrices) > 5:
                prevLastTradesVolume = int(yesterdaylastPrices[6].text.replace(',', ''))
                prevLastPrice = int(yesterdaylastPrices[1].text.replace(',', ''))
                stock_info['prevLastTradesVolume'] = prevLastTradesVolume  # 전날 15시 30분 00초 거래량
                stock_info['prevLastPrice'] = prevLastPrice  # 전날 15시 30분 00초 가격

            if len(yesterdayfirstPrices) > 5:
                prevFirstTradesVolume = int(yesterdayfirstPrices[6].text.replace(',', ''))
                # 전날 09시 01분 00초 거래량
                stock_info['prevFirstTradesVolume'] = prevFirstTradesVolume

            self.stock_info_list.update({stock: stock_info})

        print(self.stock_info_list)

        print("***************************************************************************")
        print("************************** 네시버 증시 크롤링 끝 *****************************")
        print("***************************************************************************")