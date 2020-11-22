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

if __name__ == "__main__":

    #1. 1400개의 코스닥 종목
    stock_df = pd.read_excel("./resource/코스닥.xlsx")
    df = pd.DataFrame(stock_df, columns=["회사명","종목코드"])

    print(df)