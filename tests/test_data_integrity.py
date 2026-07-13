"""
test_data_integrity.py — 시세 무결성 가드 오프라인 단위 테스트 (네트워크 불필요)

2026-07-13 KODEX200 -9.8% 데이터 오류(기초지수 KOSPI200은 -3.67%)를 재현한 표본으로,
가드가 정상일은 통과시키고 오류일은 매매를 중단시키는지 검증한다.

실행:  python tests/test_data_integrity.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.data_integrity import (
    DataIntegrityError, index_tracking_deviation,
    check_index_divergence, check_daily_move,
)


def _series(n=25, etf_base=1000.0, idx_base=100.0, drift=0.0):
    """ETF가 지수를 상수배(10.0)로 정상 추종하는 시퀀스."""
    etf, idx = [], []
    for k in range(n):
        iv = idx_base * (1 + drift) ** k
        etf.append(iv * 10.0)   # 비율 10.0 고정 = 완벽 추종
        idx.append(iv)
    return etf, idx


class TestDivergence(unittest.TestCase):
    def test_perfect_tracking_passes(self):
        etf, idx = _series()
        dev = check_index_divergence(etf, idx, lookback=20, tol=0.03)
        self.assertLess(abs(dev), 1e-6)

    def test_etf_diverges_down_raises(self):
        # 오늘의 KODEX200 사건 재현: 마지막 ETF만 -6% 이탈(지수는 정상)
        etf, idx = _series()
        etf[-1] *= 0.94
        with self.assertRaises(DataIntegrityError):
            check_index_divergence(etf, idx, lookback=20, tol=0.03)

    def test_small_deviation_within_tol_passes(self):
        etf, idx = _series()
        etf[-1] *= 0.99                       # -1% 이탈은 허용(3%) 안
        dev = check_index_divergence(etf, idx, lookback=20, tol=0.03)
        self.assertAlmostEqual(dev, -0.01, places=3)

    def test_insufficient_data_skips(self):
        etf, idx = _series(n=5)
        self.assertIsNone(check_index_divergence(etf, idx, lookback=20))

    def test_deviation_value_and_median(self):
        etf, idx = _series()
        etf[-1] *= 0.90
        dev, med = index_tracking_deviation(etf, idx, lookback=20)
        self.assertAlmostEqual(dev, -0.10, places=6)
        self.assertAlmostEqual(med, 10.0, places=6)


class TestDailyMove(unittest.TestCase):
    def test_normal_move_passes(self):
        self.assertAlmostEqual(check_daily_move([100, 103], max_move=0.25), 0.03, places=6)

    def test_extreme_move_raises(self):
        with self.assertRaises(DataIntegrityError):
            check_daily_move([100, 60], max_move=0.25)   # -40% = 1배 ETF 비현실적

    def test_short_series_skips(self):
        self.assertIsNone(check_daily_move([100]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
