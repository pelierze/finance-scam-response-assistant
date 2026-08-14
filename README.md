# AI 금융사기 응급대응 비서

금융사기 의심 상황을 구조화하고, 확인된 피해 상태에 맞는 공식 대응
지침을 우선순위대로 제공하기 위한 웹서비스 MVP입니다.

## 현재 구현 단계

Phase 1에서는 다음 안전 기반을 구현합니다.

- 외부 AI 전송 전 민감정보 마스킹
- 사용자 행동 상태와 분석 결과 데이터 모델
- 표준 라이브러리 기반 자동 테스트

전체 범위는 [MVP 구현 기획서](docs/planning/mvp-plan.md)를 참고하세요.

## 테스트

```bash
python -m pytest --cov=src
ruff check src tests
```
