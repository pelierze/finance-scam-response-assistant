# 피드백 CASE 001~050 검증 결과

기준일: 2026-08-21

- 기준 코드: `origin/main`
- 수정 코드: `fix/context-aware-action-extraction` 작업 트리
- 전체 사례: 50건
- 기준 코드 통과: 9/50
- 수정 코드 통과: 50/50

각 사례는 기대 행동 상태, 활성·금지 노출 영역, 필수·금지 추가 질문,
대표 LEVEL, 선택적 마스킹과 세부 `evidence`를 모두 비교했다.

```bash
PYTHONPATH=. python scripts/compare_feedback_cases.py --baseline-ref origin/main
```

상세 입력과 정답은 `context-cases-001-010.jsonl`부터
`context-cases-041-050.jsonl`까지의 누적 JSONL 파일이 재현 가능한 원본이다.
