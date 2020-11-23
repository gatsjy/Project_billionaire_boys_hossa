import requests
from bs4 import BeautifulSoup
from datetime import datetime,date
import pandas as pd
import os
import random
import time

#Today는 금일 날짜, dayOfTheWeek,D_day는 전일 요일,날짜
def printDayOfTheWeek (today):
    dayOfTheWeek = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    year = int(today[0:4])
    month = int(today[5:7])
    day =  int(today[-2:])-1
    D_day = f"{year}.{month}.{day}"
    D_day_3_ago = f"{year}.{month}.{day-2}"
    return dayOfTheWeek[date(year, month, day).weekday()],D_day,D_day_3_ago

if __name__ == "__main__":

    ####################################################
    ###### 변경해야 될 input data = 코스닥 excel########
    ####################################################
    stock_df = pd.read_excel("./resource/코스닥.xlsx")
    stock_list = pd.DataFrame(stock_df, columns=["회사명", "종목코드"])

    ##날짜 갖고오기 (2020.11.19)
    today = datetime.today().strftime("%Y.%m.%d")
    dayOfTheWeek,D_day,D_day_3_ago = printDayOfTheWeek (today)
    not_mentioned_stock_list = []

    ##############################test용 설정 ####################################
    stock_list = stock_list[:10]
    #stock_num_list = stock_num_list[:10]
    ##############################################################################
    
    #월요일날 실행시 금요일,토요일,일요일 뉴스 갖고오기
    if dayOfTheWeek == "일요일":
        for stock in stock_list["회사명"], stock_list["종목코드"]:
            url = f"https://search.naver.com/search.naver?where=news&query={stock}&sm=tab_opt&sort=0&photo=0&field=1&reporter_article=&pd=3&ds={D_day_3_ago}&de={D_day}&mynews=0&refresh_start=0&related=0"
            raw = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        
            #delay_time = random.random() + random.random()
            #time.sleep(delay_time)
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

        print(not_mentioned_stock_list[1])

        
    else : 
        for stock in stock_list["회사명"], stock_list["종목코드"]:
            url = f"https://search.naver.com/search.naver?where=news&query={stock}&sm=tab_opt&sort=0&photo=0&field=1&reporter_article=&pd=3&ds={today}&de={today}&mynews=0&refresh_start=0&related=0"
            raw = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})

            #delay_time = random.random() + random.random()
            #time.sleep(delay_time)
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

        print(not_mentioned_stock_list[1])

