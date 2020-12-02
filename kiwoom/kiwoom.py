"""
  * @author Gatsjy
  * @since 2020-11-26
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from PyQt5.QtTest import QTest

from config.errorCode import *

### 스케줄러 관련 ###
import schedule
##################

### telegram 관련 import ##
import telegram

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
import random
import time

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        print("Kiwoom() class start.")

        #############################################
        ## 키움 api 시작하기 전에 네이버 크롤링을 통해 원하는 데이터를 가져와서 비교하는 로직 입니다
        #############################################
        # 1. 1400개의 코스닥 종목
        stock_df = pd.read_excel("./resource/코스닥.xlsx")
        stock_df['종목코드'] = stock_df['종목코드'].apply(lambda x: "{:0>6d}".format(x))  # 종목코드 string변환
        # 2. 전 종목 뉴스 크롤링 중 언급 된 적 없는 리스트 추출
        stock_list = pd.DataFrame(stock_df, columns=["종목코드"])

        ##############################test용 설정 ####################################
        stock_list = stock_list[:100]['종목코드']
        #stock_list = stock_list['종목코드']
        ##############################################################################

        yesterdaylast = '20201201153000'
        yesterdayfirst = '20201201090100'

        # 4,5,6 조건을 담을 새로운 리스트 생성
        new_stock_num_list = []
        self.stock_info_list = {}
        info_list = {}

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
                stock_info['prevLastTradesVolume'] = prevLastTradesVolume # 전날 15시 30분 00초 거래량
                stock_info['prevLastPrice'] = prevLastPrice # 전날 15시 30분 00초 가격

            if len(yesterdayfirstPrices) > 5:
                prevFirstTradesVolume = int(yesterdayfirstPrices[6].text.replace(',', ''))
                # 전날 09시 01분 00초 거래량
                stock_info['prevFirstTradesVolume'] = prevFirstTradesVolume

            self.stock_info_list.update({stock: stock_info})

        # 9시에 돌려서 해당 현재일자의 거래량, 초기가격을 가져옵니다.
        ######### 키움관련 api 시작 ###############
        ######### event loop를 실행하기 위한 변수 모음
        self.login_event_loop = QEventLoop()  # 로그인 요청용 이벤트루프
        # self.detail_account_info_event_loop = None # 예수금 요청용 이벤트 루프
        # self.calculator_event_loop = QEventLoop()
        # self.request_stock_price = None # 업종별주가요청

        self.tradeHigh_kiwoom_db_event_loop = QEventLoop()  # 거래량 급증 이벤트 루프
        #########################################

        ### 계좌 관련된 변수 ###
        self.account_stock_dict = {}
        self.account_num = None # 계좌 번호 담아줄 변수
        self.deposit = 0 # 예수금
        self.use_money = 0 # 실제 투자에 사용할 금액
        self.use_money_percent = 0.5 # 예수금에서 실제 사용할 비율
        self.output_deposit = 0 # 출력가능 금액
        self.total_profit_loss_money = 0 # 총평가손익금액
        self.total_profit_loss_rate = 0.0 # 총수익률(%)
        #########################################

        #### 종목 분석 용
        ### 거래량 급증
        ### 0 : 종목코드 / 1 : 종목명 / 2 : 현재가 / 3 : 전일대비기호 / 4 : 전일대비 / 5 : 등락률 / 6 : 이전거래량 / 7 : 현재거래량 / 8 : 급증량
        self.calcul_data = []
        #####################
        #### 거래량 급증 종목 분석 용
        self.up_tade_volume_date = []
        ####################

        ### 요청 스크린 번호
        self.screen_my_info = "2000" # 계좌 관련한 스크린 번호
        self.screen_calculation_stock = "4000" # 계산용 스크린 번호
        ###########################################

        ########## 초기 셋팅 함수들 바로 실행
        self.get_ocx_instance() # OCX 방식을 파이썬에 사용할 수 있게 변환해주는 함수
        self.event_slots() # 키움과 연결하기 위한 시그널/슬롯 모음
        self.signal_login_commConnect() # 로그인 요청 함수 포함
        #self.get_account_info() # 계좌번호 가져오기
        #self.detail_account_info() # 예수금 요청 시그널 포함
        #self.detail_account_mystock() # 계좌평가잔고내역 가져오기
        #self.calculator_fnc()
        ############################################

        ## 파이썬 스케줄러로 각각 9시 00분 / 9시01분에 돌려야함
        self.flag1 = False
        self.flag2 = False
        schedule.every().days.at("09:00").do(self.job_0900)
        schedule.every().days.at("09:01").do(self.job_0901)
        while self.flag1 == False :
            schedule.run_pending()
            time.sleep(1)
        while self.flag2 == False :
            schedule.run_pending()
            time.sleep(1)

        ## 조건식 계산
        if self.flag2 :
            for item in self.stock_info_list.items():
                if len(item[1]) > 6:
                    todayTradesVolume = int(item[1]['todayTradesVolume'])
                    todayFirstPrice = int(item[1]['today0900Price'][1:])
                    today0900UpPercent = float(item[1]['today0900UpPercent'])
                    prevFirstTradesVolume = int(item[1]['prevFirstTradesVolume'])
                    prevLastPrice = int(item[1]['prevLastPrice'])
                    prevLastTradesVolume = int(item[1]['prevLastTradesVolume'])
                    #today0901Price = int(item[1]['today0901Price'])
                    today0901UpPercent = float(item[1]['today0901UpPercent'])
                    # 3) 전일 종가 대비 금일 시초가가 상승이 4% 미만
                    if todayFirstPrice > prevLastPrice:
                        if today0900UpPercent > 0.02 and today0900UpPercent < 4:
                            # 4) 금일 9시 00분 거래량이 전일 9시 00분 거래량보다 많다.
                            if prevFirstTradesVolume < todayTradesVolume:
                                # 5) 전일 15시 30분 거래량 보다 금일 9시 00분 거래량이 많다.
                                if prevLastTradesVolume < todayTradesVolume :
                                    #6) 금일 9시 00분 종가(=9시 01분 현재가) 대비 전일 종가 상승 4% 미만
                                    if today0901UpPercent > 0.02 and today0901UpPercent < 4:
                                        new_stock_num_list.append(item[0])

            ## telegram 푸시 메세지 관련 코드
            telgm_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
            bot = telegram.Bot(telgm_token)

            for stock in new_stock_num_list:
                # 729845849 , -1001360628906
                bot.sendMessage('-1001360628906', stock)
                # 보내고 3초동안 쉬기.. 1분에 20개의 메세지 밖에 보내지 못한다.
                time.sleep(3);

            print("-----end----") # 중단점 찍기위해서 넣어준 코드

    def get_ocx_instance(self):
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1") #레지스트리에 저장된 API 모듈 불러오기

    def event_slots(self):
        self.OnEventConnect.connect(self.login_slot) # 로그인 관련 이벤트
        self.OnReceiveTrData.connect(self.trdata_slot) # 트랜잭션 요청 관련 이벤트

    def signal_login_commConnect(self):
        self.dynamicCall("CommConnect()") # 로그인 요청 시그널

        self.login_event_loop.exec_()

    def login_slot(self, err_code):
        print(errors(err_code)[1])

        #로그인 처리가 완료됐으면 이벤트 루프를 종료한다.
        self.login_event_loop.exit()

    def get_account_info(self):
        account_list = self.dynamicCall("GetLoginInfo(QString)", "ACCNO") # 계좌번호 반환
        account_num = account_list.split(';')[0] #a;b;c -> [a,b,c]
        self.account_num = account_num
        print("계좌번호 : %s" % account_num)

    def detail_account_info(self, sPrevNext="0"):
        self.dynamicCall("SetInputValue(QString, QString)","계좌번호", self.account_num)
        self.dynamicCall("SetInputValue(QString, QString)","비밀번호", "rdx8749")
        self.dynamicCall("SetInputValue(QString, QString)","비밀번호입력매체구분", "00")
        self.dynamicCall("SetInputValue(QString, QString)","조회구분", "1")
        self.dynamicCall("CommRqData(QString, QString, int, QString)","예수금상세현황요청", "opw00001", sPrevNext, self.screen_my_info)

    def trdata_slot(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):

        if sRQName == "예수금상세현황요청":
            deposit = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "예수금")
            self.deposit = int(deposit)

            use_money = float(self.deposit) * self.use_money_percent
            self.use_money = int(use_money)
            self.use_money = self.use_money / 4

            output_deposit = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "출금가능금액")
            self.output_deposit = int(output_deposit)

            print("예수금 : %s" % self.output_deposit)
            self.stop_screen_cancel(self.screen_my_info)

        elif sRQName == "계좌평가잔고내역요청":
            total_buy_money = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총매입금액")
            self.total_buy_money = int(total_buy_money)
            total_profit_loss_money = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총평가손익금액")
            self.total_profit_loss_rate = int(total_profit_loss_money)
            total_profit_loss_rate = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총수익률(%)")
            self.total_profit_loss_rate = float(total_profit_loss_rate)

            print("계좌평가잔고내역요청 싱글데이터 : %s - %s - %s" %(total_buy_money, total_profit_loss_money, total_profit_loss_rate))
            self.stop_screen_cancel(self.screen_my_info)

            rows = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            
            for i in range(rows):
                code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목번호")
                code = code.strip()[1:]
                code_nm = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목명")
                stock_quantity = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "보유수량")
                buy_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "매입가")
                learn_rate = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "수익률(%)")
                current_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가")
                total_chegual_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "매입금액")
                possible_quantity = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "매매가능수량")

                print("종목번호 : %s - 종목명 : %s - 보유수량 : %s - 매입가 : %s - 수익률 : %s - 현재가 - %s" % (code, code_nm, stock_quantity, buy_price, learn_rate, current_price))

                if code in self.account_stock_dict:
                    pass
                else:
                    self.account_stock_dict[code] = {}

                # 보유 종목 정보를 딕셔너리에 업데이트
                code_nm = code_nm.strip()
                stock_quantity = int(stock_quantity.strip())
                buy_price = int(buy_price.strip())
                learn_rate = int(learn_rate.strip())
                current_price = int(current_price.strip())
                total_chegual_price=int(total_chegual_price.strip())
                possible_quantity =int(possible_quantity.strip())

                self.account_stock_dict[code].update({"종목명": code_nm})
                self.account_stock_dict[code].update({"보유수량": stock_quantity})
                self.account_stock_dict[code].update({"매입가": buy_price})
                self.account_stock_dict[code].update({"수익률(%)": learn_rate})
                self.account_stock_dict[code].update({"현재가": current_price})
                self.account_stock_dict[code].update({"매입금액": total_chegual_price})
                self.account_stock_dict[code].update({"매매가능수량": possible_quantity})

                print("sPreNext : %s" % sPrevNext)
                print("계좌에 가지고 있는 종목은 %s " % rows)

                if sPrevNext == "2":
                    self.detail_account_mystock(sPrevNext="2")
                else:
                    self.detail_account_info_evnet_loop.exit()

        elif sRQName == "주식일봉차트조회":
            code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "종목코드")
            cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            print("남을 일자 수 %s" % cnt)

            for i in range(cnt):
                data = []

                current_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가")
                value = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "거래량")
                trading_value = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "거래대금")
                date = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "일자")
                start_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "시가")
                high_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "고가")
                low_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "저가")

                data.append("")
                data.append(current_price.strip())
                data.append(value.strip())
                data.append(trading_value.strip())
                data.append(date.strip())
                data.append(start_price.strip())
                data.append(high_price.strip())
                data.append(low_price.strip())
                data.append("")

                print(data)
                self.calcul_data.append(data.copy())

            if sPrevNext == "2":
                self.day_kiwoom_db(code=code, sPrevNext=sPrevNext)
            else:
                print("총 일수 %s" % len(self.calcul_data))

                pass_success = False
                
                # 120일 이평선을 그릴만큼의 데이터가 있는지 체크
                if self.calcul_data == None or len(self.calcul_data) < 120:
                    pass_success = False;
                else:
                    # 120일 이평선의 최근 가격 구함
                    total_price = 0
                    for value in self.calcul_data[:120]:
                        total_price += int(value[1])
                    moving_average_price = total_price/120

                    # 오늘자 주가가 120일 이평선에 걸쳐있는지 확인
                    bottom_stock_price = False
                    check_price = None
                    if int(self.calcul_data[0][7]) <= moving_average_price and moving_average_price <= int(self.calcul_data[0][6]):
                        print("오늘의 주가가 120 이평선에 걸쳐있는지 확인")
                        bottom_stock_price = True
                        check_price = int(self.calcul_data[0][6])

                    # 과거 일봉 데이터를 조회하면서 120일 이동평균선보다 주가각 계속 밑에 존재하는지 확인
                    prev_price = None
                    if bottom_stock_price == True:
                        moving_average_price_prev = 0
                        prive_top_moving = False
                        idx = 1

                        while True:
                            if len(self.calcul_data[idx:]) < 120: # 120일 치가 있는지 계속 확인
                                print("120일 치가 없음")
                                break

                            total_price = 0
                            for value in self.calcul_data[idx:120+idx]:
                                total_price += int(value[1])
                            moving_average_price_prev = total_price / 120

                            if moving_average_price_prev <= int(self.calcul_data[idx][6]) and idx <= 20:
                                print("20일 주가가 120일 이평선과 같거나 위에 있으면 조건 통과 못 함")
                                price_top_moving = False
                                break

                            elif int(self.calcul_data[idx][7]) > moving_average_price_prev and idx > 20 : # 120일 이평선 위에 있는 구간 존재
                                print("120일치 이평선 위에 있는 구간 확인됨")
                                price_top_moving = True
                                prev_price = int(self.calcul_data[idx][7])
                                break

                            idx += 1
                            
                        # 해당부분 이평선이 가장 최근의 이평선 가격보다 낮은지 확인
                        if price_top_moving == True:
                            if moving_average_price > moving_average_price_prev and check_price > prev_price:
                                print("포착된 이평선의 가격이 오늘자 이평선 가격보다 낮은 것 확인")
                                print("포착된 부분의 일봉 저가가 오늘자 일봉의 고가보다 낮은지 확인")
                                pass_success = True

        elif sRQName == "거래량급증요청":
            cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)

            for i in range(cnt):
                data = []

                info1 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목코드")
                #info2 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목명")
                info3 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가")
                #info4 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "전일대비기호")
                #info5 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "전일대비")
                info6 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "등락률")
                #info7 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "이전거래량")
                #info8 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재거래량")
                info9 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "급증량")
                #info10 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "급증률")

                data.append(info1.strip())
                #data.append(info2.strip())
                data.append(info3.strip())
                #data.append(info4.strip())
                #data.append(info5.strip())
                data.append(info6.strip())
                #data.append(info7.strip())
                #data.append(info8.strip())
                data.append(info9.strip())
                #data.append(info10.strip())

                self.calcul_data.append(data.copy())

            print("sPreNext : %s" % sPrevNext)

            if sPrevNext == "2":
                self.tradeHigh_kiwoom_db(sPrevNext="2")
            else:
                self.tradeHigh_kiwoom_db_event_loop.exit()


    def stop_screen_cancel(self, sScrNo = None):
        self.dynamicCall("DisconnectRealData(QString)", sScrNo) # 스크린 번호 연결 끊기

    def detail_account_mystock(self, sPrevNext="0"):
        self.dynamicCall("SetInputValue(QString, QString)","계좌번호", self.account_num)
        self.dynamicCall("SetInputValue(QString, QString)","비밀번호", "rdx8749")
        self.dynamicCall("SetInputValue(QString, QString)","비밀번호입력매체구분", "00")
        self.dynamicCall("SetInputValue(QString, QString)","조회구분", "1")
        self.dynamicCall("CommRqData(QString, QString, int, QString)","계좌평가잔고내역요청", "opw00018", sPrevNext, self.screen_my_info)

        self.detail_account_info_evnet_loop = QEventLoop()
        self.detail_account_info_evnet_loop.exec_()

    # 코스닥 전체 종목 가져오는 부분
    def get_code_list_by_market(self, market_code):
        code_list = self.dynamicCall("GetCodeListByMarket(QString)", market_code)
        code_list = code_list.split(';')[:-1]
        return code_list

    def calculator_fnc(self):
        code_list = self.get_code_list_by_market("10")

        print("코스닥 갯수 %s " % len(code_list))

        for idx, code in enumerate(code_list):
            self.dynamicCall("DisconnectRealData(QString)", self.screen_calculation_stock)

            #스크린 연결 끊기
            print("%s / %s : KOSDAQ Stock : %s is updating... " % (idx+1, len(code_list), code))
            self.day_kiwoom_db(code=code) #일봉 데이터 조회

    #각 종목의 데이터를 요청합니다.
    def day_kiwoom_db(self, code=None, date=None, sPrevNext="19"):
        QTest.qWait(3600) #3.6초마다 딜레이를 준다.

        self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")

        if date != None:
            self.dynamicCall("SetInputValue(QString, QString)", "기준일자", date)

        self.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "opt10081", sPrevNext, self.screen_calculation_stock)

        self.calculator_event_loop.exec_()

    def tradeHigh_kiwoom_db(self, code=None, date=None, sPrevNext="1"):
        QTest.qWait(3600) #3.6초마다 딜레이를 준다.

        self.dynamicCall("SetInputValue(QString, QString)", "시장구분", "101")
        self.dynamicCall("SetInputValue(QString, QString)", "정렬구분", "1")
        self.dynamicCall("SetInputValue(QString, QString)", "시간구분", "1")
        self.dynamicCall("SetInputValue(QString, QString)", "거래량구분", code)
        self.dynamicCall("SetInputValue(QString, QString)", "시간", "0")
        self.dynamicCall("SetInputValue(QString, QString)", "종목조건", "0")
        self.dynamicCall("SetInputValue(QString, QString)", "가격구분", "0")
        self.dynamicCall("CommRqData(QString, QString, int, QString)","거래량급증요청", "OPT10023", sPrevNext, self.screen_my_info)

        self.tradeHigh_kiwoom_db_event_loop.exec_()

    def job_0900(self):
        ## 거래량 급증 데이터 할당 (9시 00분 조회)
        self.tradeHigh_kiwoom_db("0")  # 거래량급증요청
        for stock in self.calcul_data:
            if stock[0] in self.stock_info_list:
                self.stock_info_list[stock[0]]['today0900Price'] = stock[1]
                self.stock_info_list[stock[0]]['today0900UpPercent'] = stock[2]
            else:
                pass
        self.flag1 = True


    def job_0901(self):
        ## 거래량 급증 데이터 할당 (9시 01분 조회)
        self.tradeHigh_kiwoom_db("1")  # 거래량급증요청
        for stock in self.calcul_data:
            if stock[0] in self.stock_info_list:
                self.stock_info_list[stock[0]]['today0901Price'] = stock[1]
                self.stock_info_list[stock[0]]['today0901UpPercent'] = stock[1]
                self.stock_info_list[stock[0]]['todayTradesVolume'] = stock[3]
            else:
                pass
        self.flag2 = True

