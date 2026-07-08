import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = 'smtp.naver.com'
SMTP_PORT = 465
SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'gkswndks123@naver.com') # 본인 네이버 아이디
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD', '여기에_앱_비밀번호_입력') # 네이버 2단계 인증용 앱 비밀번호
RECEIVER_EMAIL = 'gkswndks123@naver.com'

def send_daily_report(subject, body_html):
    """HTML 형태의 매매 일지를 이메일로 전송합니다."""
    # 만약 비밀번호가 설정되지 않았다면 테스트 환경이므로 건너뜀 (예외 발생 방지)
    if SENDER_PASSWORD == '여기에_앱_비밀번호_입력' or not SENDER_PASSWORD:
        print("[Email 모듈] 이메일 비밀번호가 설정되지 않아 메일을 발송하지 않고 터미널에 출력합니다.")
        print(f"--- Title: {subject} ---")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

    html_part = MIMEText(body_html, 'html', 'utf-8')
    msg.attach(html_part)

    try:
        # 네이버 SMTP는 SSL 포트 465 사용
        smtp = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
        smtp.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        smtp.quit()
        print(f"✅ 이메일 발송 성공: {RECEIVER_EMAIL}")
        return True
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")
        return False
