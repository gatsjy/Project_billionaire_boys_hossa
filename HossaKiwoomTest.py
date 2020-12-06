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


    ###키움 api 접속하는 부분 입니다
    app = QApplication(sys.argv)
    kiwoom = Kiwoom()
    kiwoom.comm_connect()
    kiwoom.ohlcv = {"종목코드" : []}

    # OPT10023(거래량급증요청) tr 관련
    kiwoom.set_input_value("시장구분", "101")
    kiwoom.set_input_value("정렬구분", "1")
    kiwoom.set_input_value("시간구분", "2")
    kiwoom.set_input_value("거래량구분", "5")
    kiwoom.set_input_value("시간", "1")
    kiwoom.set_input_value("종목조건", "0")
    kiwoom.set_input_value("가격구분", "8")
    kiwoom.comm_rq_data("OPT10023_req", "OPT10023", 0, "0101")
    #stock_list["종목코드"]
    df = list(map(int,pd.DataFrame(kiwoom.ohlcv)["종목코드"]));

    print(df)






