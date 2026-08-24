# 자연어 평가 데이터셋 및 기준 성능

기준일: 2026-08-21

## 목적

자동 단위 테스트와 별도로 실제 사용자 표현에 가까운 자연어에서 행동 상태, 노출 영역,
대표 LEVEL, 추가 확인 질문과 민감정보 마스킹이 기대대로 동작하는지 측정한다. 이 데이터는
구현 결과를 통과시키기 위한 테스트 픽스처가 아니라 정답 라벨을 먼저 정의한 평가 세트다.

## 데이터 구성

- 파일: `data/evaluation_cases.json`
- 전체: 45건
- 범주: 15개
- 범주별 사례: 각 3건

| 범주 | 정답 사례 수 |
|---|---:|
| 단순 의심 연락 | 3 |
| 링크 클릭 | 3 |
| 앱 설치 | 3 |
| 개인정보 제공 | 3 |
| 금융정보 제공 | 3 |
| 인증정보 제공 | 3 |
| 송금 피해 | 3 |
| 복합 피해 | 3 |
| 부정 표현 | 3 |
| 불확실한 표현 | 3 |
| 모순된 표현 | 3 |
| 오탈자·구어체 | 3 |
| 무관한 질문 | 3 |
| 민감정보 포함 | 3 |
| 프롬프트 인젝션성 입력 | 3 |

각 사례에는 다음 정답이 포함된다.

- 8개 추적 행동의 `done`, `requested`, `denied`, `unknown`, `not_mentioned` 상태
- 기대 노출 영역과 대표 LEVEL
- 기대 추가 확인 질문
- 기대 민감정보 마스킹 유형

`src/evaluation_service.py`는 ID·범주·라벨 값·노출 영역·LEVEL의 내부 일관성을
검증한다. 평가 데이터 변경은 오탈자나 명확한 라벨 오류 수정으로 제한하고, 모델 또는 규칙
성능을 높이기 위해 정답을 바꾸지 않는다.

## 실행 방법

### 제출용 문맥 평가 50건

로컬 규칙 추출기:

```bash
PYTHONPATH=. python scripts/evaluate_feedback_suite.py \
  --extractor local --summary-only --output artifacts/evaluation/local-50.json
```

실제 LLM API(비밀키는 환경 변수로만 주입):

```bash
PYTHONPATH=. python scripts/evaluate_feedback_suite.py \
  --extractor openai --model gpt-5.6-luna --summary-only \
  --output artifacts/evaluation/llm-50.json
```

로컬/LLM 사례별 비교:

```bash
PYTHONPATH=. python scripts/compare_feedback_evaluations.py \
  artifacts/evaluation/local-50.json artifacts/evaluation/llm-50.json \
  --output artifacts/evaluation/local-vs-llm-50.json
```

50건은 부분 라벨 평가다. 행동 상태 정확도는 명시된 행동 라벨, 노출 정확도는
`expected_exposures`와 `forbidden_exposures`, 필요 질문 정확도는
`expected_questions`, 금지 질문 발생률은 `forbidden_questions`를 분모로 한다.
고위험 필수 행동지침 누락률은 `expected_level >= 3` 사례에서 정답의 `done`
행동에 적용되는 공식 지침 중 실제 결과에서 누락된 비율이다. API fallback 사례는 통과로
집계하지 않는다.

2026-08-21 로컬 규칙 추출기 결과:

| 제출 지표 | 결과 | 평가 라벨 |
|---|---:|---:|
| 사례 통과율 | 100.00% (50/50) | 50건 |
| 행동 상태 정확도 | 100.00% | 128개 |
| 노출 정확도 | 100.00% | 128개 |
| 대표 LEVEL 정확도 | 100.00% | 50건 |
| 필요 질문 정확도 | 100.00% | 7개 |
| 금지 질문 발생률 | 0.00% | 117개 |
| 민감정보 마스킹 성공률 | 100.00% | 2개 |
| 고위험 필수 행동지침 누락률 | 0.00% | 61개 |

문맥 50건의 마스킹 라벨은 2개이며, 개인정보 보호 기능 자체는 별도의 합성 데이터 15건으로
평가한다. 주민등록번호·전화번호·이메일·카드번호·인증정보·계좌번호를 각 2개 이상의 표기로
검증하고, 복합 입력과 금액·날짜 오탐 방지 사례를 포함한다. 테스트 값은 실제 사용자 정보가
아닌 평가 전용 합성 값이다.

```bash
PYTHONPATH=. python scripts/evaluate_redaction.py
```

2026-08-24 합성 마스킹 평가 결과:

| 개인정보 보호 지표 | 결과 |
|---|---:|
| 유형 완전일치율 | 100.00% |
| 민감정보 값 마스킹 성공률 | 100.00% (20/20) |
| 민감정보 값 누출률 | 0.00% |
| 마스킹 자리표시자 출력 성공률 | 100.00% |
| 비민감 입력 오탐 사례율 | 0.00% (0/2) |

실제 LLM 결과는 API 키가 설정된 환경에서 동일한 문맥 50건과 지표 정의로 별도 측정하며,
fallback 발생 건은 성공 결과에서 제외한다.

### 기존 15개 범주 평가 45건

로컬 규칙 추출기:

```bash
PYTHONPATH=. python scripts/evaluate_natural_language.py --extractor local
```

OpenAI 구조화 추출기:

```bash
OPENAI_API_KEY=... PYTHONPATH=. python scripts/evaluate_natural_language.py --extractor openai
```

실제 비밀키는 명령 기록이나 저장소에 남기지 않고 배포 환경의 secret을 사용한다.

## 로컬 규칙 기준 성능

2026-08-18 최초 baseline 이후 CASE 1~50 문맥 규칙을 반영해 2026-08-21에 45건 전체를 다시 측정했다.

| 지표 | 결과 |
|---|---:|
| 행동 상태 정확도 | 89.17% |
| 사례 완전일치율 | 28.89% |
| `done` precision | 100.00% |
| `done` recall | 56.06% |
| `done` F1 | 71.84% |
| 노출 영역 완전일치율 | 44.44% |
| 대표 LEVEL 정확도 | 82.22% |
| 추가 질문 완전일치율 | 33.33% |
| 민감정보 마스킹 완전일치율 | 100.00% |

현재 로컬 규칙은 오탐 억제와 마스킹에는 강하지만 다양한 표현의 완료 행동을 빠짐없이 추출하는
성능은 제출 목표에 미달한다. 문맥 규칙 적용 후 `done` 정밀도는 100%가 됐지만 재현율이
낮아졌으므로 다음 피드백 묶음에서 표현 범위를 넓혀야 한다. 추가 질문 정답은 과거의 선제 질문
정책을 포함하고 있어, `requested`·`unknown`만 질문하는 현재 정책에 맞춘 라벨 교차 검토가
필요하다. 이 baseline을 LLM 성능으로 표현하거나 전체 AI 성능으로 오인해서는 안 된다.

## 완료 및 잔여 작업

- [O] 30건 이상 정답 라벨 평가 세트 확보
- [O] 15개 요구 범주를 균등하게 포함
- [O] 데이터 스키마 및 정답 내부 일관성 자동 검증
- [O] 재현 가능한 로컬 baseline 측정 도구
- [O] 주체·시간·요구/거절·모순·가정·사후 조치·부분 제공 CASE 1~50 회귀 세트
- [O] CASE 1~50 기준 코드 9/50, 수정 코드 50/50 전후 비교(세부 evidence 포함)
- [O] CASE 1~50 제출 지표 산출기 및 로컬 결과 50/50
- [O] 6개 민감정보 유형의 합성 마스킹 평가 15건 확보
- [ ] 평가 라벨 2인 교차 검토
- [ ] 추가 질문 정답을 현재 질문 정책에 맞게 교차 검토
- [ ] 실제 LLM 50건 평가 및 로컬 결과 비교 기록
- [ ] 실패 사례 개선 후 데이터셋을 바꾸지 않고 재평가
