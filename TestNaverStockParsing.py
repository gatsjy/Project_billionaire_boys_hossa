"""
  * @author Gatsjy
  * @since 2020-11-29
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""

### telegram 관련 import ##
import telegram

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import time

TR_REQ_TIME_INTERVAL = 0.2

if __name__ == "__main__":

    #1. 1400개의 코스닥 종목
    stock_df = pd.read_excel("./resource/코스닥.xlsx")

    #2. 우선주 / 스택주 / 동전주(1000원 미만) 제외
    #2-1. 어떻게 골라낼 것인지?

    #3. 전 종목 뉴스 크롤링 중 언급 된 적 없는 리스트 추출
    today = datetime.today().strftime("%Y.%m.%d")
    stock_df = pd.read_excel("./resource/코스닥.xlsx")
    stock_list = pd.DataFrame(stock_df, columns=["회사명", "종목코드"])

    not_mentioned_stock_list = []

    ##############################test용 설정 ####################################
    #stock_list = stock_list[:10]
    ##############################################################################

    for stock in stock_list["회사명"], stock_list["종목코드"]:
        url = f"https://search.naver.com/search.naver?where=news&query={stock}&sm=tab_opt&sort=0&photo=0&field=1&reporter_article=&pd=3&ds={today}&de={today}&mynews=0&refresh_start=0&related=0"
        raw = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})

        # delay_time = random.random() + random.random()
        # time.sleep(delay_time)
        # requests응답이 없을 경우.
        if raw.status_code != requests.codes.ok:
            print("접속실패")

        html = BeautifulSoup(raw.text, "html.parser")
        news_wrappers = html.select('ul.list_news > li')

        cnt = 0

        for resources in news_wrappers:
            title = resources.select_one("a.news_tit").text
            cnt += 1

        if cnt == 0:
            not_mentioned_stock_list.append(stock)

    stock_num_list = not_mentioned_stock_list[1]
    ##############################test용 설정 ####################################
    #stock_list = stock_list[:100]
    #stock_num_list = stock_num_List[:100]
    ##############################################################################

    ### 4,5,6 조건은 네이버 주식 부분 파싱해서 결정해야 할 듯
    ##print(datetime.today().strftime("%Y%m%d0900"))
    ##print(datetime.today().strftime("%Y%m%d1530"))
    today2 = '20201124090000' # 1분으로 설정하면 첫번째 가격을 알 수 있음
    yesterdaylast  = '20201123153100' # 31분으로 설정하면 마지막 가격을 알 수 있음
    yesterdayfirst = '20201123090000' # 01분으로 설정하면 첫번째 가격을 알 수 있음

    # 4,5,6 조건을 담을 새로운 리스트 생성
    new_stock_list = list()
    new_stock_num_list = list()

    for stock in stock_num_list:
        # 오늘 거래 상세 가져오기
        todayurl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={today2}"
        raw = requests.get(todayurl, headers={'User-Agent': 'Mozilla/5.0'})
        todayurlhtml = BeautifulSoup(raw.text, "html.parser")
        todayPrices = todayurlhtml.select('body > table.type2 > tr:nth-child(3) > td > span')

        if len(todayPrices) > 5:
            todayTradesVolume = int(todayPrices[5].text.replace(',',''))
            todayFirstPrice = int(todayPrices[1].text.replace(',', ''))

        new_stock_num_list.append(stock)

    ## telegram 푸시 메세지 관련 코드
    telgm_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
    bot = telegram.Bot(telgm_token)

    for stock in new_stock_num_list:
        # 729845849 , -1001360628906
        bot.sendMessage('729845849', stock)
        # 보내고 3초동안 쉬기.. 1분에 20개의 메세지 밖에 보내지 못한다.
        time.sleep(3);
