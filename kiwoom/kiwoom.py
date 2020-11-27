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

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        print("Kiwoom() class start.")

        ######### event loop를 실행하기 위한 변수 모음
        self.login_event_loop = QEventLoop() #로그인 요청용 이벤트루프
        self.detail_account_info_event_loop = None # 예수금 요청용 이벤트 루프
        self.calculator_event_loop = QEventLoop()
        #########################################

        ### 계좌 관련된 변수 ###
        self.account_num = None # 계좌 담아줄 변수
        self.deposit = 0 # 예수금
        self.use_money = 0 # 실제 투자에 사용할 금액
        self.use_money_percent = 0.5 # 예수금에서 실제 사용할 비율
        self.output_deposit = 0 # 출력가능 금액
        self.total_profit_loss_money = 0 #총평가손익금액
        self.total_profit_loss_rate = 0.0 #총수익률(%)
        #########################################


        #### 종목 분석 용
        self.calcul_data = []
        #########################################

        ### 요청 스크린 번호
        self.screen_my_info = "2000" # 계좌 관련한 스크린 번호
        self.screen_calculation_stock = "4000" # 계산용 스크린 번호
        ###########################################


        ########## 초기 셋팅 함수들 바로 실행
        self.get_ocx_instance() # OCX 방식을 파이썬에 사용할 수 있게 변환해주는 함수
        self.event_slots() # 키움과 연결하기 위한 시그널/ 슬롯 모음
        self.signal_login_commConnect() # 로그인 요청 함수 포함
        self.get_account_info() # 계좌번호 가져오기
        self.detail_account_info() # 예수금 요청 시그널 포함
        #self.detail_account_mystock() # 계좌평가잔고내역 가져오기
        self.calculator_fnc()
        ############################################

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

            self.detail_account_info_evnet_loop.exit()

        elif sRQName == "주식일봉차트조회":
            code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "종목코드")
            data = self.dynamicCall("GetCommData(String, QString)", sTrCode, sRQName)

            if sPrevNext == "2":
                self.day_kiwoom_db(code=code, sPrevNext=sPrevNext)
            else:
                self.calculator_event_loop.exit()

            cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            print("남은 일자수 %s" % cnt)

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
                data.append("")
                data.append(value.strip())
                data.append("")
                data.append(trading_value.strip())
                data.append("")
                data.append(date.strip())
                data.append("")
                data.append(high_price.strip())
                data.append("")
                data.append(low_price.strip())

                self.calcul_data.append(data.copy())

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
            self.day_kiwoom_db(code=code)

    def day_kiwoom_db(self, code=None, date=None, sPrevNext="0"):
        QTest.qWait(3600) #3.6초마다 딜레이를 준다.

        self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")

        if date != None:
            self.dynamicCall("SetInputValue(QString, QString)", "기준일자", date)

        self.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "opt10081", sPrevNext, self.screen_calculation_stock)

        self.calculator_event_loop.exec_()
