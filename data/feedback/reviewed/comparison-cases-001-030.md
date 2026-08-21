# 피드백 CASE 001~030 검증 결과

기준일: 2026-08-21

- 기준 코드: `origin/main`
- 수정 코드: `fix/context-aware-action-extraction` 작업 트리
- 전체 사례: 30건
- 기준 코드 통과: 4/30
- 수정 코드 통과: 30/30

각 사례는 `expected_actions`, `expected_exposures`, `forbidden_exposures`,
`expected_questions`, `forbidden_questions`, `expected_level`, 선택적 마스킹과
세부 `evidence`를 모두 비교했다. LEVEL만 우연히 맞는 경우는 통과로
처리하지 않는다.

```bash
PYTHONPATH=. python scripts/compare_feedback_cases.py --baseline-ref origin/main
```

상세 입력과 정답 라벨은 `context-cases-001-010.jsonl`,
`context-cases-011-020.jsonl`, `context-cases-021-030.jsonl`이 재현 가능한 원본이다.
