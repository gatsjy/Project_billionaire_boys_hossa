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
    stock_df['종목코드'] = stock_df['종목코드'].apply(lambda x: "{:0>6d}".format(x)) #종목코드 string변환

    #2. 전 종목 뉴스 크롤링 중 언급 된 적 없는 리스트 추출
    stock_list = pd.DataFrame(stock_df, columns=["종목코드"])

    ##############################test용 설정 ####################################
    stock_list = stock_list[:10]['종목코드']
    ##############################################################################

    today2 = '20201124090000' # 1분으로 설정하면 첫번째 가격을 알 수 있음

    yesterdaylast  = '20201123153000'
    yesterdayfirst = '20201123090100'

    # 4,5,6 조건을 담을 새로운 리스트 생성
    new_stock_num_list = ()
    stock_info_list = {}

    ## * 참고 : [0] : 체결시각 [1] : 체결가 [2] : 전일비 [3] : 매도 [4] : 매수 [5] : 거래량 [6] : 변동량
    # 9시 되기전에 준비되어야 할 데이터 목록 정의
    # 9시 되기 되기 전에 가져와야 할 것
    # 전일 종가, 전일 15시 30분 변동량, 전일 9시00분 변동량,
    for stock in stock_list:
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

        stock_info = {}
        if len(yesterdaylastPrices) > 5:
            prevLastTradesVolume = int(yesterdaylastPrices[6].text.replace(',', ''))
            prevLastPrice = int(yesterdaylastPrices[1].text.replace(',', ''))
            stock_info['prevLastTradesVolume'] = prevLastTradesVolume
            stock_info['prevLastPrice'] = prevLastPrice

        if len(yesterdayfirstPrices) > 5:
            prevFirstTradesVolume = int(yesterdayfirstPrices[6].text.replace(',', ''))
            stock_info['prevFirstTradesVolume'] = prevFirstTradesVolume

        stock_info_list.update({stock:stock_info})

    # 9시 01분부터 데이터 가져와야 할 부분
    ## 스케쥴링을 통해 정확히 9시01분부터 돌리기 시작합니다...
    for stock in stock_list:
        # 오늘 거래 상세 가져오기
        todayurl = f"https://finance.naver.com/item/sise_time.nhn?code={stock}&thistime={today2}"
        raw = requests.get(todayurl, headers={'User-Agent': 'Mozilla/5.0'})
        todayurlhtml = BeautifulSoup(raw.text, "html.parser")
        todayPrices = todayurlhtml.select('body > table.type2 > tr:nth-child(3) > td > span')

        if len(todayPrices) > 5:
            todayTradesVolume = int(todayPrices[5].text.replace(',',''))
            todayFirstPrice = int(todayPrices[1].text.replace(',', ''))
            stock_info_list[stock]['todayTradesVolume'] = todayTradesVolume
            stock_info_list[stock]['todayFirstPrice'] = todayFirstPrice


    ## telegram 푸시 메세지 관련 코드
    telgm_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
    bot = telegram.Bot(telgm_token)

    for stock in new_stock_num_list:
        # 729845849 , -1001360628906
        bot.sendMessage('729845849', stock)
        # 보내고 3초동안 쉬기.. 1분에 20개의 메세지 밖에 보내지 못한다.
        time.sleep(3);
