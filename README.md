# AI 금융사기 응급대응 비서

금융사기 의심 상황을 구조화하고, 확인된 피해 상태에 맞는 공식 대응
지침을 우선순위대로 제공하기 위한 웹서비스 MVP입니다.

## MVP 기능

- 분석 전 고정 긴급 안내
- 외부 AI 전송 전 민감정보 마스킹
- 로컬 규칙과 Structured Outputs를 결합한 행동 상태 추출
- 한 차례 추가 확인과 다차원·복합 피해 상태 판단
- 공식 출처 기반 행동 지침 조합
- 복합 피해를 포함한 7개 샘플 시나리오와 장애 fallback

전체 범위는 [MVP 구현 기획서](docs/planning/mvp-plan.md)를 참고하세요.

## 공개 MVP

- Streamlit Community Cloud: https://finance-scam-response-assistant-6mgmff5zupef2elhdfsgy9.streamlit.app/
- 배포 브랜치: `main`

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
streamlit run app.py
```

`OPENAI_API_KEY`가 있으면 LLM 구조화 추출을 사용합니다. 키가 없거나 API 호출이
실패하면 주요 금융사기 표현을 지원하는 로컬 규칙 분석으로 자유 입력을 처리합니다.
로컬 분석은 범위가 제한되므로 화면에 분석 방식을 알리고 불명확한 상태는 추가 확인으로
보완합니다. `.env`와 `.streamlit/secrets.toml`은 Git에서 제외됩니다.

## 검증

```bash
python -m pytest --cov=src
ruff check app.py src tests
```

기능 기준은 [기능명세서](docs/functional-spec.md), 배포 절차는
[릴리스 체크리스트](docs/release-checklist.md)를 참고하세요.

현재 자동 테스트는 41개이며 전체 `src` 커버리지는 92%, 로컬 자연어 추출기
커버리지는 100%다. 실제 LLM 자연어 성능은 별도의 평가 데이터로 검증해야 한다.
