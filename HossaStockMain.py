"""
  * @author Gatsjy
  * @since 2020-11-22
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""
import sys

### 키움 api 관련 import ###
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
### 키움 api 관련 import ###

### telegram 관련 import ##
import telegram

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
import random
import time

TR_REQ_TIME_INTERVAL = 0.2

### 키움 api 관련 메서드 ###
class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self._create_kiwoom_instance()
        self._set_signal_slots()

    def _create_kiwoom_instance(self):
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")

    def _set_signal_slots(self):
        self.OnEventConnect.connect(self._event_connect)

    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)

    def comm_connect(self):
        self.dynamicCall("CommConnect()")
        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_()

    def _event_connect(self, err_code):
        if err_code == 0:
            print("connected")
        else:
            print("disconnected")

        self.login_event_loop.exit()

    def get_code_list_by_market(self, market):
        code_list = self.dynamicCall("GetCodeListByMarket(QString)", market)
        code_list = code_list.split(';')
        return code_list[:-1]

    def comm_rq_data(self, rqname, trcode, next, screen_no):
        self.dynamicCall("CommRqData(QString, QString, int, QString", rqname, trcode, next, screen_no)
        self.tr_event_loop = QEventLoop()
        self.tr_event_loop.exec_()

    def _get_repeat_cnt(self, trcode, rqname):
        ret = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        return ret

    def _comm_get_data(self, code, real_type, field_name, index, item_name):
        ret = self.dynamicCall("CommGetData(QString, QString, QString, int, QString", code,
                               real_type, field_name, index, item_name)
        return ret.strip()

    def _receive_tr_data(self, screen_no, rqname, trcode, record_name, next, unused1, unused2, unused3, unused4):
        if next == '2':
            self.remained_data = True
        else:
            self.remained_data = False

        if rqname == "opt10081_req":
            self._opt10081(rqname, trcode)
        elif rqname == "OPT10023_req":
            self._OPT10023(rqname, trcode)
        try:
            self.tr_event_loop.exit()
        except AttributeError:
            pass

    def _set_signal_slots(self):
        self.OnEventConnect.connect(self._event_connect)
        self.OnReceiveTrData.connect(self._receive_tr_data)

    def _opt10081(self, rqname, trcode):
        data_cnt = self._get_repeat_cnt(trcode, rqname)

        for i in range(data_cnt):
            date = self._comm_get_data(trcode, "", rqname, i, "일자")
            open = self._comm_get_data(trcode, "", rqname, i, "시가")
            high = self._comm_get_data(trcode, "", rqname, i, "고가")
            low = self._comm_get_data(trcode, "", rqname, i, "저가")
            close = self._comm_get_data(trcode, "", rqname, i, "현재가")
            volume = self._comm_get_data(trcode, "", rqname, i, "거래량")
            print(date, open, high, low, close, volume)

    def _OPT10023(self, rqname, trcode):
        data_cnt = self._get_repeat_cnt(trcode, rqname)

        for i in range(data_cnt):
            info1 = self._comm_get_data(trcode, "", rqname, i, "종목코드")
            info2 = self._comm_get_data(trcode, "", rqname, i, "종목명")
            info3 = self._comm_get_data(trcode, "", rqname, i, "현재가")
            info4 = self._comm_get_data(trcode, "", rqname, i, "가격대비")
            info5 = self._comm_get_data(trcode, "", rqname, i, "등랑률")
            info6 = self._comm_get_data(trcode, "", rqname, i, "이전거래량")
            info7 = self._comm_get_data(trcode, "", rqname, i, "현재거래량")
            info8 = self._comm_get_data(trcode, "", rqname, i, "급증량")
            info9 = self._comm_get_data(trcode, "", rqname, i, "급증률")
            #print(info1, info2, info3, info4, info5, info6,info7, info8, info9)
            self.ohlcv["종목코드"].append(info1)

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
    today2 = '202011240901' # 1분으로 설정하면 첫번째 가격을 알 수 있음
    yesterdaylast  = '202011231531' # 31분으로 설정하면 마지막 가격을 알 수 있음
    yesterdayfirst = '202011230901' # 01분으로 설정하면 첫번째 가격을 알 수 있음

    # 4,5,6 조건을 담을 새로운 리스트 생성
    new_stock_list = list()
    new_stock_num_list = list()

    for stock in stock_num_list:
        # 전일 마지막 거래 상세 가져오기
        yesterdaylasturl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={yesterdaylast}"
        raw = requests.get(yesterdaylasturl, headers={'User-Agent': 'Mozilla/5.0'})
        yesterdaylasthtml = BeautifulSoup(raw.text, "html.parser")
        yesterdaylastPrices = yesterdaylasthtml.select('body > table.type2 > tr:nth-child(3) > td > span')

        # 전일 첫번째 거래 상세 가져오기
        yesterdayfirsturl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={yesterdayfirst}"
        raw = requests.get(yesterdayfirsturl, headers={'User-Agent': 'Mozilla/5.0'})
        yesterdayfirsthtml = BeautifulSoup(raw.text, "html.parser")
        yesterdayfirstPrices = yesterdayfirsthtml.select('body > table.type2 > tr:nth-child(3) > td > span')

        # 오늘 거래 상세 가져오기
        todayurl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={today2}"
        raw = requests.get(todayurl, headers={'User-Agent': 'Mozilla/5.0'})
        todayurlhtml = BeautifulSoup(raw.text, "html.parser")
        todayPrices = todayurlhtml.select('body > table.type2 > tr:nth-child(3) > td > span')

        ## * 참고 : [0] : 체결시각 [1] : 체결가 [2] : 전일비 [3] : 매도 [4] : 매수 [5] : 거래량 [6] : 변동량
        ## 필요한 정보 1. 전일 거래량 , 금일 거래량
        ## 필요한 정보 2. 전일 종가, 금일 시가
        ## 필요한 정보 3. 전일 첫 거래량
        if len(yesterdaylastPrices) > 5:
            prevLastTradesVolume = int(yesterdaylastPrices[5].text.replace(',',''))
            prevLastPrice = int(yesterdaylastPrices[1].text.replace(',', ''))

        if len(todayPrices) > 5:
            todayTradesVolume = int(todayPrices[5].text.replace(',',''))
            todayFirstPrice = int(todayPrices[1].text.replace(',', ''))

        if len(yesterdayfirstPrices) > 5:
            prevFirstTradesVolume = int(yesterdayfirstPrices[5].text.replace(',',''))

        # 4. 전일 9시00분 거래량 < 금일 9시 00분 거래량
        if prevFirstTradesVolume < todayTradesVolume:
            # 7. 전일 15시 30분 거래량 < 금일 9시 00분 거래량
            #if prevLastTradesVolume < todayTradesVolume:
            # 5. 금일 시가(9시00분) 상승률이 전일종가대비 4% 미만
            # 5.1 위 로직을 계산하려면 하나의 조건 문이 더 추가 되어야함
            if todayFirstPrice > prevLastPrice:
                if ((todayFirstPrice-prevLastPrice) / prevLastPrice * 100) < 4:
                    new_stock_num_list.append(stock)

    ###키움 api 접속하는 부분 입니다
    app = QApplication(sys.argv)
    kiwoom = Kiwoom()
    kiwoom.comm_connect()
    kiwoom.ohlcv = {"종목코드": []}

    # OPT10023(거래량급증요청) tr 관련
    kiwoom.set_input_value("시장구분", "101")
    kiwoom.set_input_value("정렬구분", "1")
    kiwoom.set_input_value("시간구분", "2")
    kiwoom.set_input_value("거래량구분", "5")
    kiwoom.set_input_value("시간", "10")
    kiwoom.set_input_value("종목조건", "0")
    kiwoom.set_input_value("가격구분", "8")
    kiwoom.comm_rq_data("OPT10023_req", "OPT10023", 0, "0101")

    # 7. 금일 시가(9시00분) 매수세 > 매도세 -> 이건 아직도 어떤 걸 표현한 건지 모르겠다...
    ConditionSevendf = list(map(int,pd.DataFrame(kiwoom.ohlcv)["종목코드"]));
    # 두 리스트의 교집합을 찾는다
    res = list(set(ConditionSevendf).intersection(new_stock_num_list))

    ## telegram 푸시 메세지 관련 코드
    telgm_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
    bot = telegram.Bot(telgm_token)

    for stock in res:
        bot.sendMessage('-1001360628906', stock)
        # 보내고 3초동안 쉬기.. 1분에 20개의 메세지 밖에 보내지 못한다.
        time.sleep(3);
