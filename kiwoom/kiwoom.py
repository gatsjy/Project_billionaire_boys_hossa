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
import pandas as pd
### 스케줄러 관련 ###
import schedule
import datetime
##################

### telegram 관련 import ##
import telegram

import time

class Kiwoom(QAxWidget):
    def __init__(self, news_crawling_result_data):
        super().__init__()
        
        print("***************************************************************************")
        print("*********************** 키움 api 관련 시작 **********************************")
        print("***************************************************************************")

        # 전역 변수 세팅
        self.selected_stock_list = []
        self.stock_info_list = {}
        self.selected_stock_list2 = {}

        # 뉴스크롤링에서 가져온 데이터를 할당 합니다.
        df = pd.DataFrame(news_crawling_result_data)
        for stock in df.values:
            # [0] : 회사명
            # [1] : 종목ID
            # [2] : 전일종가 prevLastPrice
            # [3] : 전일 첫 거래량 prevFirstTradesVolume
            # [4] : 전일 마지막 거래량 prevLastTradesVolume
            # print(stock)
            stock_info = {}
            stock_info['stockName'] = stock[0]
            stock_info['prevLastPrice'] = stock[2]
            stock_info['prevFirstTradesVolume'] = stock[3]
            stock_info['prevLastTradesVolume'] = stock[4]
            self.stock_info_list.update({stock[1]: stock_info})

        ######### event loop를 실행하기 위한 변수 모음
        self.login_event_loop = QEventLoop()  # 로그인 요청용 이벤트루프
        # self.detail_account_info_event_loop = None # 예수금 요청용 이벤트 루프
        # self.calculator_event_loop = QEventLoop()
        # self.request_stock_price = None # 업종별주가요청
        self.tradeHigh_kiwoom_db_event_loop = None
        self.trade_present_kiwoom_db_event_loop = None  ## 시가대비등락률요청
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

        ## 파이썬 스케줄러로
        self.flag1 = False
        self.flag2 = False
        self.flag3 = False
        #schedule.every().days.at("09:00:57").do(self.job_0900_1)
        #schedule.every().days.at("09:01:30").do(self.job_0900_2)
        schedule.every().days.at("09:00:00").do(self.job_0900_1)
        schedule.every().days.at("09:00:57").do(self.job_0900_2)

        while self.flag1 == False:
            schedule.run_pending()
            time.sleep(1)
        while self.flag2 == False:
            schedule.run_pending()
            time.sleep(1)

        ## 조건식 계산
        if self.flag2:
            for item in self.stock_info_list.items():
                if len(item[1]) > 7:
                    prevFirstTradesVolume = int(item[1]['prevFirstTradesVolume'])
                    prevLastPrice = int(item[1]['prevLastPrice'])
                    prevLastTradesVolume = int(item[1]['prevLastTradesVolume'])

                    todayTradesVolume = int(item[1]['todayTradesVolume'])
                    today0900Price = int(item[1]['today0900Price'][1:])
                    today0900UpPercent = float(item[1]['today0900UpPercent'])

                    # 2020-12-08, 한주안, 금일 시초가 추가
                    #today0900StartPrice = int(item[1]['today0900StartPrice'][1:])
                    if(item[1]['today0900StartPrice'][0] == '+' or item[1]['today0900StartPrice'][0] == '-'):
                        today0900StartPrice = int(item[1]['today0900StartPrice'][1:])
                    else:
                        today0900StartPrice = int(item[1]['today0900StartPrice'])

                    # 1번째 조건
                    # 3) 전일 종가 대비 금일 시초가가 상승이 4% 미만
                    # 0.02 < (금일 시가 - 어제 종가) / 어제 종가 * 100 > 4
                    if today0900StartPrice > prevLastPrice:
                        if (today0900StartPrice-prevLastPrice)/prevLastPrice*100 > 0.02 and (today0900StartPrice-prevLastPrice)/prevLastPrice*100 < 4:
                            # 4) 금일 9시 00분 거래량이 전일 9시 00분 거래량보다 많다.
                            if prevFirstTradesVolume < todayTradesVolume:
                                # 5) 전일 15시 30분 거래량 보다 금일 9시 00분 거래량이 많다.
                                if prevLastTradesVolume < todayTradesVolume:
                                    #6) 금일 9시 00분 종가(=9시 01분 현재가) 대비 전일 종가 상승 4% 미만
                                    if today0900UpPercent > 0.02 and today0900UpPercent < 4:
                                        #7) 매수세, 매도세 관련 조건 추가 (0900현재가 - 금일 시가) > 0)
                                        if today0900Price-today0900StartPrice > 0:
                                            self.selected_stock_list.append(item[0])
                                            ## 2020-12-16, 한주안, 로그데이터 추가
                                            selected_stock_info = {}
                                            selected_stock_info['prevFirstTradesVolume'] = prevFirstTradesVolume
                                            selected_stock_info['prevLastPrice'] = prevLastPrice
                                            selected_stock_info['prevLastTradesVolume'] = prevLastTradesVolume
                                            selected_stock_info['todayTradesVolume'] = todayTradesVolume
                                            selected_stock_info['today0900Price'] = today0900Price
                                            selected_stock_info['today0900UpPercent'] = today0900UpPercent
                                            selected_stock_info['today0900StartPrice'] = today0900StartPrice
                                            selected_stock_info['stockId'] = item[0]
                                            self.selected_stock_list2.update({item[0]: selected_stock_info})

            ## telegram 푸시 메세지 관련 코드
            telgm_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
            bot = telegram.Bot(telgm_token)

            bot.sendMessage('-1001360628906', '======= 조건 종목 =======')
            for stock in self.selected_stock_list:
                # 729845849(나한테 보내기) , -1001360628906(호싸 채팅방)
                bot.sendMessage('-1001360628906', stock)
                # 보내고 3초동안 쉬기.. 1분에 20개의 메세지 밖에 보내지 못한다.
                time.sleep(3.5);

            bot.sendMessage('-1001360628906', '======= 조건 종목(상세데이터) =======')
            for stock in self.selected_stock_list2.items():
                # 729845849(나한테 보내기) , -1001360628906(호싸 채팅방)
                bot.sendMessage('-1001360628906', stock)
                # 보내고 3초동안 쉬기.. 1분에 20개의 메세지 밖에 보내지 못한다.
                time.sleep(3.5);

            print("-----end----")

            ## 09:03
            schedule.every().days.at("09:05:00").do(self.job_0905)
            #schedule.every().days.at("12:05:00").do(self.job_0905)
            while self.flag3 == False:
                schedule.run_pending()
                time.sleep(1)

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

                # 120일 이평선을 그릴만큼의 데이터가 있는지 체크
                if self.calcul_data == None or len(self.calcul_data) < 120:
                    pass_success = False;

        elif sRQName == "거래량급증요청":
            cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)

            for i in range(cnt):
                data = []

                info1 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목코드")
                info3 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가")
                info6 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "등락률")
                info9 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "급증량")

                data.append(info1.strip())
                data.append(info3.strip())
                data.append(info6.strip())
                data.append(info9.strip())

                self.calcul_data.append(data.copy())
                print(data)

            print("sPreNext : %s" % sPrevNext)

            if sPrevNext == "2":
                self.tradeHigh_kiwoom_db(sPrevNext=sPrevNext)
            else:
                self.tradeHigh_kiwoom_db_event_loop.exit()

        elif sRQName == "시가대비등락률요청":
            cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)

            for i in range(cnt):
                data = []

                info1 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목코드")
                info2 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목명")
                info3 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "시가")
                info4 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가")
                info5 = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재거래량")

                data.append(info1.strip())
                data.append(info2.strip())
                data.append(info3.strip())
                data.append(info4.strip())
                data.append(info5.strip())

                self.calcul_data.append(data.copy())
                print(data)

            print("sPreNext : %s" % sPrevNext)

            if sPrevNext == "2":
                self.trade_present_kiwoom_db(sPrevNext=sPrevNext)
            else:
                self.trade_present_kiwoom_db_event_loop.exit()

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

    ## 09:00 실행되는 job
    def tradeHigh_kiwoom_db(self, code=None, date=None, sPrevNext=None):
        QTest.qWait(3600) #3.6초마다 딜레이를 준다.

        self.dynamicCall("SetInputValue(QString, QString)", "시장구분", "101")
        self.dynamicCall("SetInputValue(QString, QString)", "정렬구분", "1")
        self.dynamicCall("SetInputValue(QString, QString)", "시간구분", "1")
        self.dynamicCall("SetInputValue(QString, QString)", "거래량구분", "0")
        self.dynamicCall("SetInputValue(QString, QString)", "시간", "0")
        self.dynamicCall("SetInputValue(QString, QString)", "종목조건", "0")
        self.dynamicCall("SetInputValue(QString, QString)", "가격구분", "0")
        self.dynamicCall("CommRqData(QString, QString, int, QString)","거래량급증요청", "OPT10023", sPrevNext, self.screen_my_info)

        # 다음 코드가 진행되지 않도록 이벤트 루프를 실행해서 다음 코드가 실행되지 않게 막는다.
        self.tradeHigh_kiwoom_db_event_loop.exec_()

    ## 2020-12-08, 한주안, 09:00 실행되는 job_2 (시가대비등락률요청)
    def trade_present_kiwoom_db(self, code=None, date=None, sPrevNext=None):
        QTest.qWait(3600) #3.6초마다 딜레이를 준다.

        self.dynamicCall("SetInputValue(QString, QString)", "정렬구분", "1")
        self.dynamicCall("SetInputValue(QString, QString)", "거래량조건", "0000")
        self.dynamicCall("SetInputValue(QString, QString)", "시장구분", "101")
        self.dynamicCall("SetInputValue(QString, QString)", "상하한포함", "0")
        self.dynamicCall("SetInputValue(QString, QString)", "종목조건", "4")
        self.dynamicCall("SetInputValue(QString, QString)", "신용조건", "0")
        self.dynamicCall("SetInputValue(QString, QString)", "거래대금조건", "3")
        self.dynamicCall("SetInputValue(QString, QString)", "등락조건", "1")
        self.dynamicCall("CommRqData(QString, QString, int, QString)","시가대비등락률요청", "opt10028", sPrevNext, self.screen_my_info)

        # 다음 코드가 진행되지 않도록 이벤트 루프를 실행해서 다음 코드가 실행되지 않게 막는다.
        self.trade_present_kiwoom_db_event_loop.exec_()

    #2020-12-14, 한주안, 추가
    def job_0900_1(self):
        print("##########################################")
        print("##########################################")
        print("***************job_0900_1 시작**************")
        print("###############거래량급증요청################")
        print("종목코드/현재가/등락률/급증량")
        print("##########################################")
        print(datetime.datetime.now())
        print("##########################################")
        self.tradeHigh_kiwoom_db_event_loop = QEventLoop()
        self.tradeHigh_kiwoom_db(sPrevNext="0")  # 거래량급증요청

        for stock in self.calcul_data:
            if stock[0] in self.stock_info_list:
                self.stock_info_list[stock[0]]['today0900Price'] = stock[1]
                self.stock_info_list[stock[0]]['today0900UpPercent'] = stock[2]
                #2020-12-07, 한주안, (수정) 용태가 원하는 것은 0900의 거래량이였음
                self.stock_info_list[stock[0]]['todayTradesVolume'] = stock[3]
            else:
                pass
        self.flag1 = True
        self.calcul_data.clear();

    def job_0900_2(self):
        ## 거래량 급증 데이터 할당 (9시 00분 조회)
        print("##########################################")
        print("##########################################")
        print("***************job_0900_2 시작**************")
        print("###############시가대비등락률###############")
        print("종목코드/종목명/시가/현재가/현재거래량")
        print("##########################################")
        print(datetime.datetime.now())
        print("##########################################")
        self.trade_present_kiwoom_db_event_loop = QEventLoop()
        self.trade_present_kiwoom_db(sPrevNext="0")  # 시가대비등락률요청

        for stock in self.calcul_data:
            if stock[0] in self.stock_info_list:
                self.stock_info_list[stock[0]]['today0900StartPrice'] = stock[2]
            else:
                pass
        self.flag2 = True
        self.calcul_data.clear();

    def job_0905(self):
        print("##########################################")
        print("##########################################")
        print("***************job_0905 시작**************")
        print("###############시가대비등락률###############")
        print("종목코드/종목명/시가/현재가/현재거래량")
        print("##########################################")
        print(datetime.datetime.now())
        print("##########################################")
        self.trade_present_kiwoom_db_event_loop = QEventLoop()
        self.trade_present_kiwoom_db(sPrevNext="0")  # 시가대비등락률요청

        for stock in self.calcul_data:
            if stock[0] in self.stock_info_list:
                self.stock_info_list[stock[0]]['today0903Price'] = stock[3]
                self.stock_info_list[stock[0]]['today0903TradeVolume'] = stock[4]
            else:
                pass
        self.flag3 = True
        self.calcul_data.clear();