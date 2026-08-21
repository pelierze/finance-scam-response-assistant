# 사용자 문장 피드백 데이터

웹서비스 검토 과정에서 수집한 자연어 문장, 실제 분석 결과와 기대 결과를 기존 제출용 평가 세트(`data/evaluation_cases.json`)와 분리해 관리한다.

## 폴더 구조

- `incoming/`: 아직 정답 라벨과 피드백 검토가 끝나지 않은 사례
- `reviewed/`: 기대 상태와 수정 방향을 검토·확정한 사례

검토가 끝난 사례 중 회귀 테스트나 공식 평가에 사용할 항목만 별도 검증 후 `data/evaluation_cases.json` 또는 테스트 코드로 옮긴다.

현재 `reviewed/context-cases-001-010.jsonl`과 `reviewed/context-cases-011-020.jsonl`에
정답 행동·노출·추가 질문·마스킹 기대치를 기록했으며, 자동 회귀
테스트가 이름 규칙에 맞는 모든 파일을 누적해 읽는다.
동일 사례의 사용자 입력만 한 줄씩 복사해 수동 테스트할 수 있도록 `reviewed/test-inputs.txt`도 함께 관리한다. 새 사례 묶음을 검토할 때 해당 파일 끝에 같은 순서로 입력을 추가한다.
기준 코드와 수정 코드의 상태·질문·노출 결과는 `scripts/compare_feedback_cases.py`로 비교하며,
최신 결과는 `reviewed/comparison-cases-001-020.md`에 기록한다.

```bash
PYTHONPATH=. python scripts/compare_feedback_cases.py --baseline-ref origin/main
```

`reviewed/context-cases-011-020.jsonl`처럼 같은 이름 규칙으로 파일을 추가하면 모든 검토 사례를 자동으로 누적 비교한다.

## 권장 파일 형식

여러 사례를 누적하기 쉬운 UTF-8 JSON Lines(`.jsonl`) 형식을 사용한다. 회귀
파일명은 `context-cases-NNN-NNN.jsonl` 형식으로 추가한다.

```json
{"id":"CASE-021","input":"앱을 설치하고 송금했어요","expected_actions":{"app_installed":"done","money_transferred":"done"},"expected_exposures":["device","financial_loss"],"forbidden_exposures":[],"expected_questions":[],"forbidden_questions":["app_installed","money_transferred"],"expected_level":5}
```

각 행에는 최소한 다음 정보를 기록한다.

- `id`: 중복되지 않는 사례 ID
- `input`: 사용자가 검토한 문장
- `expected_actions`: 검증할 행동별 기대 상태
- `expected_exposures` / `forbidden_exposures`: 반드시 활성화되거나 활성화되면 안 되는 노출 영역
- `expected_questions` / `forbidden_questions`: 반드시 나와야 하거나 나오면 안 되는 추가 질문
- `expected_level`: 기대 대표 LEVEL
- `expected_evidence_contains`: 상위 행동 축 안에 보존되어야 할 세부 사실 문구
- `expected_redacted_types` / `forbidden_redacted_types`: 선택적 마스킹 검증 항목

## 개인정보 보호

- 실제 주민등록번호, 계좌번호, 카드번호, 전화번호, 이메일, 비밀번호와 인증번호를 저장하지 않는다.
- 민감정보가 포함된 사례는 `[주민등록번호 마스킹]`, `[계좌번호 마스킹]` 같은 자리표시자로 치환한 후 저장한다.
- 실제 피해자의 이름, 연락처, 금융회사 고객번호 등 재식별 가능한 정보도 제거한다.
- 원본 대화나 운영 로그를 이 폴더에 그대로 복사하지 않는다.
