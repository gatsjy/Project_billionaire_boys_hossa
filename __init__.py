"""
  * @author Gatsjy
  * @since 2020-11-27
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""
import sys
from crawling.crawling import *
from kiwoom.kiwoom import *
from PyQt5.QtWidgets import *

class Main():
    def __init__(self):
        print("Main() start")
        self.app = QApplication(sys.argv) #PyQt5로 실행할 파일명을 자동 설정
        self.kiwoom = Kiwoom() #키움 클래스 객체화
        self.app.exec_() #이벤트 루프 실행

if __name__ == "__main__":
    print("***************************************************************************")
    print("*********************** 프로그램 메인 시작 ***********************************")
    print("***************************************************************************")
    
    # 뉴스 크롤링 시작하는 부분
    crawling = crawling()
    #print(crawling.result_data)

    # 키움 api 관련 시작
    Main()



