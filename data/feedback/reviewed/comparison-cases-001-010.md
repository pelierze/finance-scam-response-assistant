# 피드백 사례 전후 비교

- 기준 코드: `origin/main` (`f561066`)
- 수정 코드: `fix/context-aware-action-extraction` 작업 트리
- 비교일: 2026-08-21
- 전체 사례: 10건
- 기준 코드 통과: 0/10
- 수정 코드 통과: 10/10

| CASE | 기준 코드 | 수정 코드 | 기대 상태 | 기준 | 수정 |
|---|---|---|---|---:|---:|
| CASE-001 | contact=unknown, link=done | contact=done, link=denied | contact=done, link=denied | X | O |
| CASE-002 | link=unknown, app=done | link=done, app=unknown | link=done, app=unknown | X | O |
| CASE-003 | contact/link/app/financial/auth=done, money=not_mentioned | 모두 done | 모두 done | X | O |
| CASE-004 | link=done, app=unknown, auth=not_mentioned, money=unknown | link/app=done, auth/money=denied | link/app=done, auth/money=denied | X | O |
| CASE-005 | money=done | money=unknown | money=unknown | X | O |
| CASE-006 | app=done, personal=unknown, financial=not_mentioned | app=not_mentioned, personal/financial=denied | app=not_mentioned, personal/financial=denied | X | O |
| CASE-007 | app=done, money=unknown | app/money=denied | app/money=denied | X | O |
| CASE-008 | contact=done, app=requested, financial=denied | contact=done, app/financial=denied | contact=done, app/financial=denied | X | O |
| CASE-009 | app/auth=done | app=done, auth=denied | app=done, auth=denied | X | O |
| CASE-010 | app/personal/money=done | app/money=done, personal=denied | app/money=done, personal=denied | X | O |

## 판정 기준

각 사례는 다음 세 항목이 모두 기대값과 일치해야 통과한다.

- 기대 행동 상태
- 추가 질문 목록
- `done` 행동으로 계산한 활성 노출 집합

## 재실행

```bash
PYTHONPATH=. python scripts/compare_feedback_cases.py --baseline-ref origin/main
```

`data/feedback/reviewed/context-cases-*.jsonl`에 새 묶음을 추가하면 별도 코드 수정 없이 누적 비교한다.
