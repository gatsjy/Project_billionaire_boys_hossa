import requests

def send_telegram_message(message):
    """
    텔레그램 봇을 통해 메시지를 전송합니다.
    2020년 억만장자 보이즈 클럽 프로젝트에 있던 과거 토큰과 챗봇 ID를 재사용합니다.
    """
    bot_token = "1308465026:AAHOrMFyULrupxEnhkPIsNjGJ0o-4uF0q7U"
    chat_id = "-1001360628906"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("텔레그램 메시지 전송 성공!")
    except Exception as e:
        print(f"텔레그램 메시지 전송 실패: {e}")

if __name__ == "__main__":
    send_telegram_message("🤖 억만장자 보이즈 클럽 봇 테스트 메시지입니다.")
