# Project_billionaire_boys_hossa

- 파이썬 기본 문법 공부하기
    - [x]  2020-11-22 : 파이썬을 이용해서 키움 api 접근하는 방법에 대해서 알아보기
    - [x]  2020-11-22 : 사용하려고 하는 계산식에 필요한 정보 끌어올 수 있는지 확인하기
    - [ ]  2020-11-23 : 프로그램 첫 구동 / 내가 사용하고 있는 조건식이 유용한지 체크하기
    - [ ]  2020-11-23 :  

## 1. 환경설정 관련
- 키움 API 에 접속이 안되던 문제..
- 해결법 1. 버전호환이 안되서 그럼 [https://grand-unified-engine.tistory.com/5](https://grand-unified-engine.tistory.com/5) 참고
- 해결법 2. 관리자로 접근 안해서 그럼 [https://www.codingfactory.net/11743](https://www.codingfactory.net/11743)
- 파이썬, 아나콘다 32비트로 다운 받아야지 실행된다고함 (난 처음부터 32비트로 다운 받은 상태였음..)

 

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
    - [ ]  파이썬으로 파싱 및 로직이 처리되고 나면 API형식으로 자바로 데이터 보내줘서 그걸 토대로 웹이 보여줄 수 없을까?
    - [ ]  속도를 개선할 수 있는 방안이 없을까?
    - [ ]  날짜 예외처리하기 (월요일이면 이전주 금요일의 데이터를 처리하도록 수정하는 로직 필요) 
