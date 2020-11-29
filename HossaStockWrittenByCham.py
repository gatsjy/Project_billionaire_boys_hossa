import requests
from bs4 import BeautifulSoup
from datetime import datetime,date
import pandas as pd
import os
import random
import time
import FinanceDataReader as fdr

#Today는 금일 날짜, dayOfTheWeek,D_day는 전일 요일,날짜
def printDayOfTheWeek (today):
    dayOfTheWeek = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    year = int(today[0:4])
    month = int(today[5:7])
    day =  int(today[-2:])
    D_day_1_ago = f"{year}.{month}.{day-1}"
    D_day_2_ago = f"{year}.{month}.{day-2}"
    D_day_3_ago = f"{year}.{month}.{day-3}"
    return dayOfTheWeek[date(year, month, day).weekday()],D_day_1_ago,D_day_3_ago,D_day_2_ago

if __name__ == "__main__":

    ####################################################
    ###### 변경해야 될 input data = 코스닥 excel########
    ####################################################
    stock_df = pd.read_excel("./resource/코스닥.xlsx")
    stock_df['종목코드'] = stock_df['종목코드'].apply(lambda x: "{:0>6d}".format(x)) #종목코드 string변환
    stock_list = pd.DataFrame(stock_df, columns=["회사명", "종목코드"])

    ##날짜 갖고오기 (2020.11.19)
    today = datetime.today().strftime("%Y.%m.%d")
    dayOfTheWeek,D_day_1_ago,D_day_3_ago,D_day_2_ago = printDayOfTheWeek(today)
    
    ##조건0. OUTPUT = raw_step_data, 코스닥 종목+종가 가격 데이터
    if dayOfTheWeek == "월요일":
        Close_list = [fdr.DataReader(f"{x}",D_day_3_ago,D_day_3_ago)["Close"] for x in stock_list["종목코드"]]
        raw_df=pd.DataFrame(Close_list)
        Close_df=pd.DataFrame(raw_df.values, columns=[f"{D_day_3_ago}_종가"])
        raw_step_data = pd.concat([stock_list,Close_df],axis=1)
        print("raw 조건 종목 개수 :",len(raw_step_data))

        ##조건1. OUTPUT = first_step_data, 동전주 1200이상 적용
        first_step_data=raw_step_data[raw_step_data[f"{D_day_3_ago}_종가"] >= 1200]
        print("첫번째 조건 종목 개수 :",len(first_step_data),"_동전주 1200이상 적용")


    elif dayOfTheWeek == "일요일":
        Close_list = [fdr.DataReader(f"{x}",D_day_2_ago,D_day_2_ago)["Close"] for x in stock_list["종목코드"]]
        raw_df=pd.DataFrame(Close_list)
        Close_df=pd.DataFrame(raw_df.values, columns=[f"{D_day_2_ago}_종가"])
        raw_step_data = pd.concat([stock_list,Close_df],axis=1)
        print("raw 조건 종목 개수 :",len(raw_step_data))

        ##조건1. OUTPUT = first_step_data, 동전주 1200이상 적용
        first_step_data=raw_step_data[raw_step_data[f"{D_day_2_ago}_종가"] >= 1200]
        print("첫번째 조건 종목 개수 :",len(first_step_data),"_동전주 1200이상 적용")

    else : 
        Close_list = [fdr.DataReader(f"{x}",D_day_1_ago,D_day_1_ago)["Close"] for x in stock_list["종목코드"]]
        raw_df=pd.DataFrame(Close_list)
        Close_df=pd.DataFrame(raw_df.values, columns=[f"{D_day_1_ago}_종가"])
        raw_step_data = pd.concat([stock_list,Close_df],axis=1)
        print("raw 조건 종목 개수 :",len(raw_step_data))

        ##조건1. OUTPUT = first_step_data, 동전주 1200이상 적용
        first_step_data=raw_step_data[raw_step_data[f"{D_day_1_ago}_종가"] >= 1200]
        print("첫번째 조건 종목 개수 :",len(first_step_data),"_동전주 1200이상 적용")
       
    
    
    ##############################test용 설정 ####################################
    raw_step_data = raw_step_data[:10]
    ##############################################################################
   

    ##조건2. OUTPUT = second_step_data, 뉴스 크롤링, 전날 뉴스 0건인 자료
    not_mentioned_stock_list = []
    #월요일날 실행시 금요일,토요일,일요일 뉴스 갖고오기
    if dayOfTheWeek == "월요일":
        for stock in stock_list["회사명"]:
            url = f"https://search.naver.com/search.naver?where=news&query={stock}&sm=tab_opt&sort=0&photo=0&field=1&reporter_article=&pd=3&ds={D_day_3_ago}&de={D_day_1_ago}&mynews=0&refresh_start=0&related=0"
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

        print(not_mentioned_stock_list[:])

        
    else : 
        for stock in stock_list["회사명"]:
            url = f"https://search.naver.com/search.naver?where=news&query={stock}&sm=tab_opt&sort=0&photo=0&field=1&reporter_article=&pd=3&ds={D_day_1_ago}&de={D_day_1_ago}&mynews=0&refresh_start=0&related=0"
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

        print(not_mentioned_stock_list[:])
        
   
    print("두번째 조건 종목 개수 :",len(not_mentioned_stock_list),"_뉴스크롤링")
    isin_filter =first_step_data["회사명"].isin(not_mentioned_stock_list)
    second_step_data = first_step_data[isin_filter]                                 #조건2. OUTPUT = second_step_data
