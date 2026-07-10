# 📈 억만장자 보이즈 클럽 (Billionaire Boys Club) — hossa

**정직한 백테스트로 검증된 것만 굴리는, 한국 지수 추세추종 코어 봇**

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Status](https://img.shields.io/badge/status-Paper_Trading-brightgreen)

<br>

## 🚀 개요 (Overview)

본래 조선·원전·방산 테마주 1분 단타 + 인버스 헷징을 노린 봇이었으나, **2026-07 정직성 개편**에서
모든 개별주/단타 전략이 비용·갭·표본외 검증을 통과하지 못하고 지수 단순보유에 패배함을 확인했다.
그 결과 봇의 정체성을 **"검증된 지수 추세추종 코어"** 로 재편했다.

> 이 프로젝트의 원칙: **그럴듯한 아이디어를 검증 없이 배포하지 않는다.**
> 매 전략은 비용 반영 + 훈련/검증(walk-forward) 관문을 통과해야만 라이브에 오른다.
> 상세 연구·판정 로그: [progress.md](progress.md) §9~16, [EXPERT_REVIEW.md](EXPERT_REVIEW.md).

<br>

## 💼 현행 라이브 전략 — 지수 추세추종 코어 (`index_core_bot.py`)

매 영업일 장 마감 후 1회 실행. KODEX 200을 추세에 따라 보유하고, 방어 구간엔 단기채로 캐리를 번다.

### 규칙
| 구성 | 내용 |
|---|---|
| **대상** | KODEX 200 (069500) · 방어 슬리브 KODEX 단기채권 (153130) |
| **추세 판별** | 이평 앙상블(120/150/200일선) ±2% 히스테리시스 밴드 |
| **목표 비중** | 강세 이평 비율로 **주식 20~100% 연속**, 나머지는 단기채 방어 |
| **진입/방어** | 매수(비중 확대)는 34%씩 **분할**, 방어(축소)는 **즉시 전량** (비대칭) |
| **비용** | ETF 거래세 면제(tax=0) + 수수료·슬리피지 반영 |
| **안전장치** | 200일선 재생(결정론적·멱등), 시세 신선도/이상치 검증, 별도 장부·락, 1시간 중복실행 방지 |

### 검증 성적 (KODEX 200, 훈련~2019 / 검증2020~, 비용반영)
| 설계 | 훈련 Calmar | 검증 Calmar | 훈련 MDD |
|---|---|---|---|
| 단순보유(B&H) | 0.18 | 0.80 | -23.1% |
| 단일 200MA(초기 코어) | 0.21 | 1.07 | -20.3% |
| **앙상블 + 단기채 방어(현행)** | **0.38** | **1.18** | **-15.1%** |

낙폭을 방어하며 추세를 따르는 것이 목적. **강세장 의존적이며 "무조건 이기는 전략"이 아님**(정직 고지).

<br>

## 🗂️ 코드 구성

**라이브**
- `index_core_bot.py` — 지수 코어 봇(2자산 리밸런서). 매 영업일 1회 실행.
- `run_index_core.bat` — Windows 작업 스케줄러용 런처.
- `backtest/index_trend_strategy.py` — 추세 판별(앙상블 밴드) + 목표비중.
- `backtest/params.py` — 모든 매매 파라미터 단일소스(SSOT).
- `portfolio_manager.py` — 장부 로드/저장(원자적) + 락. `backtest/realistic.py` — 비용/갭 인지 백테스트 코어.

**연구 (backtest/, `scratch_*`) — 판정 근거**
- `optimizer.py` / `hold_research.py` — 테마 단타·청산설계: **전부 OOS 음수(폐기)**.
- `reversal_research.py` / `entry_quality_research.py` / `portfolio_backtest.py` — 스윙 반전: 건당 통과했으나 **포트폴리오에서 지수에 패배(폐기)**.
- `kr_trend_research.py` / `dual_momentum_research.py` — 지수 추세·듀얼모멘텀 검증.
- `kr_event_study.py` — 뉴스/이벤트 회피 전제 검증: **효과 미미(구축 보류)**.
- `index_enhancement_research.py` — 현행 코어 개선(방어 슬리브+앙상블) 검증.

**은퇴 (파일 보존, 라이브 중단)** — `radar_alert.py`, `start_radar_daemon.py`, `run_daily.py`,
`backtest/strategy.py`, `backtest/reversal_strategy.py` 등 개별주/인버스 계열.

<br>

## ▶️ 실행

```bash
# 수동 1회 실행
python index_core_bot.py

# 매 영업일 15:40 자동 실행 등록(Windows) — 사용자가 직접 1회
schtasks /Create /TN "HossaIndexCoreBot" /TR "<repo>\run_index_core.bat" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:40 /F
```
장부는 `portfolio_index.json`(지수 코어 전용, 기존 테마 `portfolio.json`과 분리). 이메일 설정은 `config.json`(git 제외).

<br>

## 🎯 로드맵 / 남은 검증 후보
- [ ] 방어·유휴 현금의 안전 캐리 최적화(파킹형/CD금리 ETF).
- [ ] 변동성 타게팅(실현변동성 역비례 노출)으로 Sharpe 개선 — 별도 검증 조건.
- [ ] 방어자산 금(KODEX 골드) 추가 다변화 — 별도 검증 조건.
- [ ] 실계좌 연동(키움 OpenAPI)은 **충분한 페이퍼 검증 이후에만.**

<br>

---

## 📅 과거 개발 히스토리 (Archived)
<details>
<summary>👉 2020년 초기 프로젝트 일지</summary>

- `2020-11-22`: 키움 API 접근·데이터 추출 타당성 검토
- `2020-11-24`: 강남역 1차 모임 (조건 확인 및 API 사용 확정)
- `2020-11-25`: 동전주/우선주 필터링 및 뉴스 크롤링 로직 (by cham)
- `2020-11-30`: 2차 모임 (스케줄링 로직 도입)
- `2020-12-07`: 텔레그램 봇 연동 및 거래량 조건 세분화
- *(2026-07 정직성 개편으로 개별주 단타 전면 폐기 → 지수 추세추종 코어로 재편)*
</details>
