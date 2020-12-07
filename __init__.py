"""
  * @author Gatsjy
  * @since 2020-11-27
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""
import sys
from crawling.NewsCrawling import *
from crawling.NaverStockCrawling import *
from kiwoom.kiwoom import *
from PyQt5.QtWidgets import *

class Main():
    def __init__(self):
        print("***************************************************************************")
        print("*********************** 프로그램 메인 시작 ***********************************")
        print("***************************************************************************")


if __name__ == "__main__":
    
    # 뉴스 크롤링 시작하는 부분
    newscrawling = NewsCrawling()

    # 네이버 증권 크롤링 시작하는 부분
    # 데이터 검증해보니 딱히 네이버 크롤링을 할 필요를 못느낌 -> 뉴스 크롤링 부분에서 원하는 데이터 전부 가져옴
    # 2020-12-07, 한주안, (수정) 용태와 의논해본 끝에 원하는 데이터는 전날 1530분의 거래량이 아니라 모든 거래가 끝나고 난 뒤의 거래량이였음..
    # naverStockCrawling = NaverStockCrawling(newscrawling.news_crawling_result_data);
    # print(newscrawling.news_crawling_result_data)

    # 키움 api 관련 시작
    app = QApplication(sys.argv)  # PyQt5로 실행할 파일명을 자동 설정
    kiwoom = Kiwoom(newscrawling.news_crawling_result_data)  # 키움 클래스 객체화
    app.exec_()  # 이벤트 루프 실행



