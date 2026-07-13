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

매 영업일 장 마감 후 1회 실행. KODEX 200을 추세에 따라 보유하고, 방어 구간엔 달러·단기채로 갈아탄다.

### 규칙 (3자산 리밸런서)
| 구성 | 내용 |
|---|---|
| **대상** | 주식 KODEX 200 (069500) · 폭락헷지 KODEX 미국달러선물 (261240) · 캐리 KODEX 단기채권 (153130) |
| **추세 판별** | 이평 앙상블(120/150/200일선) ±2% 히스테리시스 밴드 |
| **목표 비중** | 강세 이평 비율로 **주식 20~100% 연속**. 방어분(1−주식)은 달러:단기채로 분할 |
| **상시 헷지** | **달러 5% 항상 보유**(tail hedge) — 강세장에도 초기 급락 쿠션(Phase 18) |
| **진입/방어** | 매수(비중 확대)는 34%씩 **분할**, 방어(축소)는 **즉시** (비대칭) |
| **비용** | ETF 거래세 면제(tax=0) + 수수료·슬리피지 반영 |
| **안전장치** | 앙상블 재생(결정론적·멱등), **장부 자가감사**·**시세 무결성 가드**(ETF↔지수 괴리·일간변동), 신선도 검증, 별도 장부·락, 1시간 중복실행 방지, 실행주체(scheduler/manual) 기록 |

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
- `index_core_bot.py` — 지수 코어 봇(3자산 리밸런서). 매 영업일 1회. **매매 전 장부 자가감사 + 시세 무결성 가드**.
- `run_index_core.bat` — Windows 스케줄러용 런처. ⚠️ **ASCII 전용**(한글 넣으면 cmd 파싱 붕괴로 조용히 죽음).
- `backtest/index_trend_strategy.py` — 추세 판별(앙상블 밴드) + 목표비중 + 시세 무결성 검사.
- `backtest/params.py` — 모든 매매 파라미터 단일소스(SSOT).
- `portfolio_manager.py` — 장부 로드/저장(원자적) + 락. `backtest/realistic.py` — 비용/갭 인지 백테스트 코어.

**실계좌 연동 대비 (2026-07-13)**
- `backtest/ledger_audit.py` — 장부 자가감사(이력 재생 = 보유·현금 대사). 실패 시 매매 중단+경보.
- `backtest/data_integrity.py` — 시세 무결성(ETF↔기초지수 괴리 3%↑, 일간변동 25%↑ 시 매매 중단). *2026-07-13 KODEX 데이터 오류 -9.8%를 실제 차단.*
- `broker/` — 매매 실행 어댑터. `base.py`(Broker 인터페이스) · `paper_broker.py`(가상 장부) · `kiwoom_broker.py`(키움 REST 모의/실전) · `make_broker(config)` 팩토리로 `mode` 한 줄 전환.
- `kiwoom_connect_test.py` — 키움 모의투자 연결검증(토큰→잔고→현재가, 읽기전용).
- `tests/` — 오프라인 단위테스트 25개(감사·무결성·브로커). `python tests/test_*.py`.

**연구 (backtest/, `scratch_*`) — 판정 근거**
- `optimizer.py` / `hold_research.py` — 테마 단타·청산설계: **전부 OOS 음수(폐기)**.
- `reversal_research.py` / `entry_quality_research.py` / `portfolio_backtest.py` — 스윙 반전: 건당 통과했으나 **포트폴리오에서 지수에 패배(폐기)**.
- `kr_trend_research.py` / `dual_momentum_research.py` — 지수 추세·듀얼모멘텀 검증.
- `kr_event_study.py` — 뉴스/이벤트 회피 전제 검증: **효과 미미(구축 보류)**.
- `index_enhancement_research.py` — 현행 코어 개선(방어 슬리브+앙상블) 검증.

**검증 의존 모듈(연구 스크립트가 참조하므로 유지)** — `backtest/strategy.py`(테마 돌파),
`backtest/reversal_strategy.py`(스윙 반전), `backtest/data_loader.py`.

> 🧹 은퇴한 테마/인버스 **라이브 코드**(`radar_alert.py`, `start_radar_daemon.py`, `run_daily.py`,
> `liquidate.py`, `backtest/engine.py`·`simulator.py`·`inverse_simulator.py`·`index_strategy.py`·
> `macro_indicators.py`)와 옛 주변 모듈(kiwoom/crawling/telegram/config), 빌드 캐시·IDE 설정은
> 2026-07 정리에서 **삭제**했습니다(git 히스토리로 복구 가능). 죽은 전략의 검증 기록은
> `backtest/*_research.py`와 [progress.md](progress.md)에 남아 있습니다.

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

## 🔌 실계좌 연동 로드맵 (키움 REST API)
페이퍼→실계좌는 **키움 REST API**(구 OpenAPI+ 아님 — REST는 64bit·크로스플랫폼)로 간다.
봇 판단 로직은 무변경, `broker/` 어댑터의 구현체만 교체.

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 브로커 어댑터 골격(base + PaperBroker + 팩토리) | ✅ 완료 |
| 2 | KiwoomRestBroker(모의) + 연결테스트 | ✅ 구현(사용자 모의 앱키로 검증 대기) |
| 3 | 일일 대사(브로커 잔고 vs 장부) | ⬜ |
| 4 | 주문 생명주기·킬스위치·일일 한도 가드 | ⬜ |
| 5 | 봇을 `make_broker`로 배선 | ⬜ |

**사용자 액션:** [openapi.kiwoom.com](https://openapi.kiwoom.com)에서 앱키·시크릿 + **모의투자** 신청 →
`config.json`에 kiwoom 섹션(`config.example.json` 참고) → `python kiwoom_connect_test.py`.
**실전(live)은 모의 충분검증 + 대사·킬스위치 완료 후에만.**

## 🎯 전략 로드맵 / 남은 검증 후보
- [ ] 방어·유휴 현금의 안전 캐리 최적화(파킹형/CD금리 ETF).
- [ ] 변동성 타게팅(실현변동성 역비례 노출)으로 Sharpe 개선 — 별도 검증 조건.
- [ ] 방어자산 금(KODEX 골드) 추가 다변화 — 별도 검증 조건.
- [ ] (보류) 펀더멘털/팩터: krx-fundamentals-api는 **현재 스냅샷만**이라 팩터 백테스트 look-ahead 함정. 시점 데이터 재구성 없이는 무기 아님.

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
