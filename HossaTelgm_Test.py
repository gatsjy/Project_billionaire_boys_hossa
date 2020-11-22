"""
  * @author Gatsjy
  * @since 2020-11-22
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""

import telegram

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
import random
import time


if __name__ == "__main__":

# telegram 관련 코드
    telgm_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
    bot = telegram.Bot(telgm_token)

    bot.sendMessage('-1001360628906', 'test')
    #print(stock_list)
    #print(stock_num_list)
    #B_LIST

    ###키움 api 접속하는 부분 입니다
    #app = QApplication(sys.argv)
    #kiwoom = Kiwoom()
    #kiwoom.comm_connect()
