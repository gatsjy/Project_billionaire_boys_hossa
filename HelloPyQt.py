"""
  * @author Gatsjy
  * @since 2020-11-22
  * realize dreams myself
  * Blog : https://blog.naver.com/gkswndks123
  * Github : https://github.com/gatsjy
"""

import sys
from PyQt5.QtWidgets import *

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyStock")
        self.setGeometry(300, 300, 300, 400)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mywindow = MyWindow()
    mywindow.show()
    app.exec_()