import requests
from bs4 import BeautifulSoup
from datetime import datetime,date
import pandas as pd
import os
import random
import time
import FinanceDataReader as fdr
from dateutil.relativedelta import *
import selenium
from selenium import webdriver
import telegram

#Today는 금일 날짜, dayOfTheWeek,D_day는 전일 요일,날짜
def printDayOfTheWeek (today):
    dayOfTheWeek = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    year = int(today[0:4])
    month = int(today[5:7])
    day =  int(today[-2:])
    return dayOfTheWeek[date(year, month, day).weekday()]

#날짜 포맷 바꾸기(yyyy-mm-dd -> yyyy.mm.dd)
def format_change(today):
    year = str(today[0:4])
    month = str(today[5:7])
    day =  str(today[-2:])
    return f"{year}.{month}.{day}"

#날짜 포맷 바꾸기(yyyy.mm.dd -> yyyymmdd)
def format_change_1(today):
    year = str(today[0:4])
    month = str(today[5:7])
    day =  str(today[-2:])
    return f"{year}{month}{day}"

if __name__ == "__main__":

    ####################################################
    ###### 변경해야 될 input data = 코스닥 excel########
    ####################################################
    stock_df = pd.read_excel("./resource/코스닥.xlsx")
    stock_df['종목코드'] = stock_df['종목코드'].apply(lambda x: "{:0>6d}".format(x)) #종목코드 string변환
    stock_list = pd.DataFrame(stock_df, columns=["회사명", "종목코드"])

    ##날짜 갖고오기 (2020.11.19)
    today = format_change(str(datetime.now().date()+relativedelta(days=-0)))
    dayOfTheWeek = printDayOfTheWeek(today)
    D_day_1_ago = format_change(str(datetime.now().date()+relativedelta(days=-1)))
    D_day_2_ago = format_change(str(datetime.now().date()+relativedelta(days=-2)))
    D_day_3_ago = format_change(str(datetime.now().date()+relativedelta(days=-3)))
    
    ##조건0. OUTPUT = raw_step_data, 코스닥 종목+종가 가격 데이터
    # 요일에 따른 종가 데이터 불러오는 시점 다름 (월요일,일요일 -> 금요일, 나머지 ->전일 )
    if dayOfTheWeek == "월요일":
        D_day = D_day_3_ago

    elif dayOfTheWeek == "일요일":
        D_day = D_day_2_ago

    else : 
        D_day = D_day_1_ago
        
    Close_list = [fdr.DataReader(f"{x}",D_day,D_day)["Close"] for x in stock_list["종목코드"]]
    raw_df=pd.DataFrame(Close_list)
    Close_df=pd.DataFrame(raw_df.values, columns=[f"{D_day}_종가"])
    raw_step_data = pd.concat([stock_list,Close_df],axis=1)
    print("raw 조건 종목 개수 :",len(raw_step_data))

    ##조건1. OUTPUT = first_step_data, 동전주 1200이상 적용
    first_step_data=raw_step_data[raw_step_data[f"{D_day}_종가"] >= 1200]
    print("첫번째 조건 종목 개수 :",len(first_step_data),"_동전주 1200이상 적용")


    ##############################test용 설정 ####################################
    raw_step_data = raw_step_data[:10]
    ##############################################################################
   

    ##조건2. OUTPUT = second_step_data, 뉴스 크롤링, 전날 뉴스 0건인 자료
    not_mentioned_stock_list = []
    search_list_cnt = 0 #동적크롤링 설정을 위해 0번째 종목의 경우 네이버 뉴스 내 검색옵션버튼 누르도록 함.

    #월요일날 실행시 금요일,토요일,일요일 뉴스 갖고오기

    ######################동적 크롤링 추가####################
    chrome_path = r'C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe' # -> 크롤링용 chromedriver다운로드 및 경로설정
    browser = webdriver.Chrome(chrome_path)
    time.sleep(2)

    for stock in first_step_data["회사명"]:
        url = f"https://search.naver.com/search.naver?where=news&query={stock}&sm=tab_opt&sort=0&photo=0&field=0&reporter_article=&pd=3&ds={D_day}&de={D_day_1_ago}&docid=&nso=&mynews=1&mynews=0&refresh_start=0&related=0#"
        browser.get(url)
        time.sleep(1)
        search_list_cnt +=1

        # 언론사 선정을 위한 뉴스 동적크롤링
        if search_list_cnt ==1:
            press_ok_box = browser.find_element_by_xpath('//*[@id="snb"]/div/ul/li[7]/div/a')
            press_ok_box.click()
            time.sleep(0.1)

            press_box = browser.find_element_by_xpath('//*[@id="snb"]/div/ul/li[5]/a')
            press_box.click()
            time.sleep(0.3)

            press_box_economy = browser.find_element_by_xpath('//*[@id="order_cat"]/div[1]/div/a[3]')
            press_box_economy.click()
            time.sleep(0.1)

            press_box_economy_all = browser.find_element_by_xpath('//*[@id="order_cat"]/div[4]/div[1]/div')
            press_box_economy_all.click()
            time.sleep(0.1)

            press_ok_box = browser.find_element_by_xpath('//*[@id="snb"]/div/ul/li[5]/div/span/span[1]/button')
            press_ok_box.click()
            time.sleep(0.1)

        #first_input data
        news_count_list = []
        source = browser.page_source
        html = BeautifulSoup(source,"html.parser")
        news_wrappers = html.select('ul.list_news > li')
        cnt = 0

        for resources in news_wrappers:
            title = resources.select_one("a.news_tit").text
            cnt += 1
            #print(title)  #<- 기사 잘 나오는지 확인 위함

        if cnt == 0:
            not_mentioned_stock_list.append(stock)

    #print(not_mentioned_stock_list[:]) 크롤링 결과 종목 데이터 출력       
    browser.close() # 동적 크롤링 위한 크롬 창 닫기
    print("두번째 조건 종목 개수 :",len(not_mentioned_stock_list),"_뉴스크롤링")
    isin_filter =first_step_data["회사명"].isin(not_mentioned_stock_list)
    second_step_data = first_step_data[isin_filter] #조건2. OUTPUT = second_step_data
    
    ###########9시00분 거래량, 15시30분 거래량###############
    D_day_non_format= format_change_1(D_day)
    yesterday_start_data = f'{D_day_non_format}0901' # 1분으로 설정하면 첫번째 가격을 알 수 있음
    yesterday_last_data = f"{D_day_non_format}1531"  # 31분으로 설정하면 마지막 가격을 알 수 있음
    
    new_stock_start_volume = [] # 9시00분 거래량
    new_stock_last_volume = []  # 15시30분 거래량
    
    for stock_code in second_step_data["종목코드"]:
        todayurl = f"https://finance.naver.com/item/sise_time.nhn?code={stock_code}&thistime={yesterday_start_data}"
        raw = requests.get(todayurl, headers={'User-Agent': 'Mozilla/5.0'})
        todayurlhtml = BeautifulSoup(raw.text, "html.parser")
        todayPrices = todayurlhtml.select('body > table.type2 > tr:nth-child(3) > td > span')
        if len(todayPrices) > 5:
            todayTradesVolume = int(todayPrices[6].text.replace(',',''))
            todayFirstPrice = int(todayPrices[1].text.replace(',', ''))
        new_stock_start_volume.append(todayTradesVolume)

        todayurl = f"https://finance.naver.com/item/sise_time.nhn?code={stock_code}&thistime={yesterday_last_data}"
        raw = requests.get(todayurl, headers={'User-Agent': 'Mozilla/5.0'})
        todayurlhtml = BeautifulSoup(raw.text, "html.parser")
        todayPrices = todayurlhtml.select('body > table.type2 > tr:nth-child(3) > td > span')
        if len(todayPrices) > 5:
            todayTradesVolume = int(todayPrices[6].text.replace(',',''))
            todayFirstPrice = int(todayPrices[1].text.replace(',', ''))
        new_stock_last_volume.append(todayTradesVolume)

    volume_dict = {"종목코드": second_step_data["종목코드"], "9:00_거래량" : new_stock_start_volume,"15:30_거래량" : new_stock_last_volume}
    volume_df = pd.DataFrame(volume_dict)    
    result_data = pd.merge(second_step_data, volume_df, how='inner', on=None)
