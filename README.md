# Project_billionaire_boys_hossa

- 개발 히스토리 내역
    - [x]  2020-11-22 : 파이썬을 이용해서 키움 api 접근하는 방법에 대해서 알아보기
    - [x]  2020-11-22 : 사용하려고 하는 계산식에 필요한 정보 끌어올 수 있는지 확인하기
    - [x]  2020-11-23 : 프로그램 첫 구동 / 내가 사용하고 있는 조건식이 유용한지 체크하기 / 참이랑 git 연동 완료
    - [x]  2020-11-24 : 호싸 주식 프로젝트 강남역 첫번째 모임 / 조건 확인, API 사용 여부 확인
    - [x]  2020-11-25 : 기본종목데이터 + 조건1. 동전주/스택주/우선주 + 조건2. 뉴스 크롤링 (해당 코드 구동 시간 : 30분) written by cham
    - [x]  2020-11-26 : 계좌가져오기, 예수금 확인 로직 추가
    - [x]  2020-11-27 : 프로젝트 단위로 코드 분할, 코스닥 전체 종목 가져오는 로직 추가, 일봉 데이터 가져오는 로직 추가
    - [x]  2020-11-28 : OPT10023(거래량급증요청) 관련 데이터 불러오기 로직 추가
    - [x]  2020-11-29 : 코스닥 데이터 불러와서 조건에 맞는 데이터 추출 후 비교하는 로직 추가
    - [x]  2020-11-30 : 호싸 주식 프로젝트 두번째 모임 / 조건 데이터 확인 작업 / 스케줄링 코드 추가 (0900, 0901)
    - [x]  2020-12-03 : (첫번째시도) 스케줄링 해서 원하는 데이터 뿌려주기 -> 실패
    - [x]  2020-12-06 : 참 크롤링 + 주안 키움 api 합쳐서 테스트 준비 
    - [x]  2020-12-07 : (두번째시도) 스케줄링 해서 원하는 데이터 텔레그램으로 푸시 메세징 -> 10가지 항목 추출 용태랑 의논 후 조건 수정 
                         네오팩트(290660), 모바일리더(100030), 덕산하이메탈(77360), 디지아이(43360), 동성화인텍(33500) .. 총 10가지
                         ## 2020-12-07, 한주안, (수정 전) 전일 15:30 거래량 -> (수정 후) 전일 15:30 거래량 + 장 마감하고 나서 진행되는 거래량을 더한다.(ex 15:35, 15:40.. 등등)
                         ## 2020-12-07, 한주안, (수정 전) 0901의 거래량 -> (수정 후) 0900의 거래량 // 용태가 원하는 것은 0900의 거래량
    - [ ]  2020-12-08 : (세번째시도)

## 1. 환경설정 관련
- 키움 API 에 접속이 안되던 문제..
- 해결법 1. 버전호환이 안되서 그럼 [https://grand-unified-engine.tistory.com/5](https://grand-unified-engine.tistory.com/5) 참고
- 해결법 2. 관리자로 접근 안해서 그럼 [https://www.codingfactory.net/11743](https://www.codingfactory.net/11743)
- 파이썬, 아나콘다 32비트로 다운 받아야지 실행된다고함 (난 처음부터 32비트로 다운 받은 상태였음..)
- financedataReader 다운 -> pip install -U finance-datareader

## 2. 네이버 검색 : 코스닥 해당 종목이 뉴스 제목에 언급된 적이 있는지 판단하기

```python
stock_df = pd.read_excel("./resource/코스닥.xlsx")

    #2. 우선주 / 스택주 / 동전주(1000원 미만) 제외
    #2-1. 어떻게 골라낼 것인지?

    #3. 전 종목 뉴스 크롤링 중 언급 된 적 없는 리스트 추출
    today = datetime.today().strftime("%Y.%m.%d")
    stock_df = pd.read_excel("./resource/코스닥.xlsx")
    stock_list = pd.DataFrame(stock_df, columns=["회사명", "종목코드"])
    ##날짜 갖고오기 (2020.11.19)
    today = datetime.today().strftime("%Y.%m.%d")

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
```

## 3. 네이버 주식 : 전일 가격과 금일 가격 전일 거래량 금일 거래량 등 파악

```python
today2 = '202011200901' # 1분으로 설정하면 첫번째 가격을 알 수 있음
    yesterdaylast = '202011191531' # 31분으로 설정하면 마지막 가격을 알 수 있음
    yesterdayfirst = '202011190901' # 31분으로 설정하면 마지막 가격을 알 수 있음

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
            # 5. 금일 시가(9시00분) 상승률이 전일종가대비 4% 미만
            # 5.1 위 로직을 계산하려면 하나의 조건 문이 더 추가 되어야함
            if todayFirstPrice > prevLastPrice:
                if ((todayFirstPrice-prevLastPrice) / prevLastPrice * 100) < 4:
                    # 6. 금일 9시00분 종가가 4% 미만 ( 뭐에 기준에서 4% 미만인지?)
                    new_stock_num_list.append(stock)
```

### 4. 키움 API : 실시간 급등주 관련해서 파악하기(OPT10023) ==> *해당 사항은 추후 논의가 필요함

```python
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
```

## 5. 텔레그램 봇으로 그룹 메세지 푸시하기

```python
## telegram 푸시 메세지 관련 코드
    telgm_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
    bot = telegram.Bot(telgm_token)

    for stock in res:
        bot.sendMessage('-1001360628906', stock)
        # 보내고 3초동안 쉬기.. 1분에 20개의 메세지 밖에 보내지 못한다.
        time.sleep(3);
```

## 6. 후 순위 개발 사항
- TO_DO_LIST
    - [ ]  파이썬으로 파싱 및 로직이 처리되고 나면 rest api로 데이터 만들어서 웹서버로 보내 정보 시각화 해줄 수 있는 기능
    - [ ]  속도를 개선할 수 있는 방안이 없을까?
    - [ ]  날짜 예외처리하기 (월요일이면 이전주 금요일의 데이터를 처리하도록 수정하는 로직 필요) 
    - [ ]  뽑아 낸 종목 자동매매 수익률 2% 넘으면 자동매매
    - [ ]  1초안에 끝내는 로직...

## 7. 참고자료
[수익률 관련 데이터 모음](https://www.notion.so/aa79a56240ab4ff7a21d8c36907b61e4)

## 8. 조건 목록
1) 동전주/스텍주/우량주 --> 동전주 ==예정
2) 뉴스크롤링 == 완료

9시 되기 전에 준비해둬야 할 데이터
(네이버 크롤링으로 9시 이전에 긁어오기) -> 키움통해 가져올 수 있는 부분이 있을까?
-> 거래량급증으로 전일로 해서 구해도 어느 정보를 거래량으로 두어야할지 모르겠음..
- 전날 15시 30분 00초 가격
- 전날 15시 30분 00초 거래량
- 전날 09시 01분 00초 거래량

-- 9시00분~9시00분59초
-- 9시00분에 거래량 급증에서 분을 0으로 넣고 조회 한다.
-- 데이터중에 '등락률' 이 0.02(초과)~4%(미만)
3) 전일 종가 대비 금일 시초가가 상승이 4%미만

-- 9시01분~9시01분59초
-- 9시01분에 거래량 급증에서 분을 1으로 넣고 조회 한다.
: 뽑아올 데이터 : 급증량, 현재가  
4) 금일 9시 00분 거래량이 전일 9시 00분 거래량보다 많다.
- 어제 변동량보다 오늘 급증량이 크다
    ※거래량 기준 = 9시 00분~9시 01분 거래량

5) 전일 15시 30분 거래량 보다 금일 9시 00분 거래량이 많다.
    ※거래량 기준 = 9시 00분~9시 01분 거래량

-- 데이터중에 등락률이 0.02%초과~ 4%미만 
6) 금일 9시 00분 종가(=9시 01분 현재가) 대비 전일 종가 4프로 상승 미만 

**** 이 부분을 tr에서 찾아야 한다.
7) 금일 9시 00분 종가일때 매수세가 매도세보다 센 것 -> 9시1분일때 파란거??
  -> 9시 01분 일때 매수세가 매도세보다 센 것
   (어떤 TR에서 불러오는지 확인 필요)

** 오늘 해결해야 할점
- 이전날의 데이터는 어디서 불러오는가? -> 네이버 크롤링으로 가져온다
