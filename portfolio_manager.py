import os
import json
import time
import tempfile
import contextlib
from datetime import datetime

try:
    import fcntl  # POSIX(mac/linux) 파일 락
    _HAS_FCNTL = True
except ImportError:  # 윈도우 폴백
    _HAS_FCNTL = False

PORTFOLIO_FILE = 'portfolio.json'
LOCK_FILE = 'portfolio.lock'

DEFAULT_PF = {
    "initial_capital": 2000000,
    "cash": 2000000,
    "holdings": [],
    "trade_history": [],
}


@contextlib.contextmanager
def portfolio_lock():
    """
    장부(portfolio.json)에 대한 배타적 락.

    레이더 데몬(1분 주기)과 EOD 결산(run_daily)이 같은 파일을 동시에
    read-modify-write 하면 매매기록/현금이 유실된다. 이 락으로 임계구역을 보호한다.

    사용:
        with portfolio_lock():
            pf = load_portfolio()
            ... 수정 ...
            save_portfolio(pf)
    """
    if not _HAS_FCNTL:
        # 윈도우: 락 파일 존재 여부로 간이 상호배제(폴링)
        for _ in range(300):  # 최대 ~30초 대기
            try:
                fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.close(fd)
                break
            except FileExistsError:
                time.sleep(0.1)
        try:
            yield
        finally:
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
        return

    f = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_PF))  # 깊은 복사본


def save_portfolio(pf):
    """원자적 저장: 임시파일에 쓴 뒤 os.replace 로 교체(중간 크래시에도 장부 안 깨짐)."""
    target_dir = os.path.dirname(os.path.abspath(PORTFOLIO_FILE)) or '.'
    fd, tmp = tempfile.mkstemp(dir=target_dir, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(pf, f, ensure_ascii=False, indent=2)
        os.replace(tmp, PORTFOLIO_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def business_days_between(start_date_str, end_dt=None):
    """
    start_date(YYYY-MM-DD) 이후 흐른 '영업일' 수(주말 제외, 공휴일 미반영 근사).
    타임스탑을 캘린더일이 아니라 영업일로 판정하기 위함(금요일 매수→월요일이 1영업일).
    """
    start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end = (end_dt or datetime.today()).date()
    if end <= start:
        return 0
    days = 0
    import datetime as _dt
    cur = start
    one = _dt.timedelta(days=1)
    while cur < end:
        cur += one
        if cur.weekday() < 5:  # 월(0)~금(4)
            days += 1
    return days
