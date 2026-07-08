import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_email_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    if not os.path.exists(config_path):
        print("config.json 파일이 없습니다. 이메일을 전송할 수 없습니다.")
        return None
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f).get('email_config')

def send_daily_report(date, body_markdown):
    """일일 매매 결과 요약 이메일 발송"""
    config = get_email_config()
    if not config: return
    
    sender_email = config['sender_email']
    sender_password = config['sender_password']
    receiver_email = config['receiver_email']
    
    msg = MIMEMultipart()
    msg['Subject'] = f"[Billionaire Boys] {date} 자동매매 일지 브리핑"
    msg['From'] = sender_email
    msg['To'] = receiver_email
    
    # Markdown -> 간단한 Text로 변환해서 발송
    msg.attach(MIMEText(body_markdown, 'plain', 'utf-8'))
    
    try:
        # 네이버 메일은 SSL 포트 465 사용
        server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("일일 매매 일지 이메일 전송 성공!")
    except Exception as e:
        print(f"이메일 전송 실패: {e}")

def send_radar_alert(subject, message):
    """장중 10분 타점 레이더 긴급 알림 이메일 발송"""
    config = get_email_config()
    if not config: return
    
    sender_email = config['sender_email']
    sender_password = config['sender_password']
    receiver_email = config['receiver_email']
    
    msg = MIMEMultipart()
    msg['Subject'] = f"🚨 [타점 레이더] {subject}"
    msg['From'] = sender_email
    msg['To'] = receiver_email
    
    msg.attach(MIMEText(message, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print(f"타점 알림 이메일 전송 성공: {subject}")
    except Exception as e:
        print(f"타점 알림 이메일 전송 실패: {e}")
