# OpenAI API 동작 확인 가이드

이 문서는 API 키 값을 저장소에 남기지 않고 Streamlit 배포와 로컬 환경에서
OpenAI Responses API 연결을 확인하는 절차를 설명한다.

## 1. API 키 파일 필요 여부

배포 환경에는 API 키 파일이 필요하지 않다. Streamlit Community Cloud의 앱 설정에서
다음 값을 **최상위 secret**으로 등록한다.

```toml
OPENAI_API_KEY = "실제 키"
OPENAI_MODEL = "gpt-5.6-luna"
```

`OPENAI_MODEL`은 선택 항목이다. 생략하면 애플리케이션 기본값인
`gpt-5.6-luna`를 사용한다.

다음 파일과 값은 Git에 커밋하지 않는다.

- `.streamlit/secrets.toml`
- `.env`
- API 키가 포함된 화면 캡처, 로그, 문서
- 셸 명령 결과에 출력된 API 키

현재 `.gitignore`는 `.env`와 `.streamlit/secrets.toml`을 제외한다.

## 2. Streamlit 배포에서 확인

1. Streamlit Community Cloud에서 앱의 **Settings → Secrets**를 연다.
2. `OPENAI_API_KEY`가 섹션 내부가 아닌 최상위에 등록됐는지 확인한다.
3. 저장 후 앱을 재부팅하거나 재배포한다.
4. 앱 공개 범위를 확인한다. 로그인하지 않은 시크릿 브라우저에서 URL이 열려야 한다.
5. 앱에서 샘플이 아닌 **직접 입력**을 선택한다.
6. 실제 개인정보가 없는 다음 문장을 입력한다.

   `검찰이라고 전화가 와서 앱 설치를 요구했지만 설치하지 않았습니다.`

7. **상황 분석하기**를 누른다.

결과 위에 **“AI 분석이 완료되었습니다.”**와 **“OpenAI API의 구조화 응답을 검증한
결과입니다.”**가 표시되면 OpenAI 호출과 스키마 검증이 성공한 것이다.

다음 안내는 서로 다른 실행 경로를 의미한다.

| 화면 안내 | 의미 |
|---|---|
| AI 분석이 완료되었습니다 | API 호출 및 Structured Outputs 검증 성공 |
| AI 연결이 원활하지 않아 로컬 규칙으로 분석 | 키·한도·네트워크·모델·응답 검증 문제로 fallback |
| 현재는 주요 금융사기 표현을 인식하는 로컬 규칙 분석 | 실행 환경에 API 키가 없음 |
| 샘플 모드 | 사전 정의 결과 사용, API를 호출하지 않음 |

추가로 OpenAI Platform의 Usage 화면에서 테스트 시각에 요청 사용량이 증가했는지
확인하면 실제 과금 API 호출 여부를 교차 확인할 수 있다.

## 3. 로컬에서 확인

셸 환경 변수로 키를 주입한다.

```bash
export OPENAI_API_KEY="실제 키"
export OPENAI_MODEL="gpt-5.6-luna"
streamlit run app.py
```

또는 Git에서 제외된 `.streamlit/secrets.toml`을 로컬에 만들 수 있다. 최상위 secret은
Streamlit 실행 시 환경 변수로도 제공된다. 파일을 새로 만든 뒤에는 Streamlit 서버를
재시작한다.

테스트가 끝나면 현재 셸에서 키를 제거한다.

```bash
unset OPENAI_API_KEY
```

## 4. 장애 경로 확인

API 키를 저장소에서 삭제하거나 잘못된 키를 커밋하는 방식으로 시험하지 않는다.
필요하면 별도 테스트 환경에서 secret을 일시적으로 제거한 뒤 앱을 재시작한다. 직접 입력
분석 시 로컬 분석 안내가 나오고 고정 긴급 안내와 공식 대응 지침이 유지되는지 확인한다.

## 5. 제출 전 확인

- 공개 URL이 로그인 없이 열리는가
- 직접 입력에서 OpenAI API 성공 안내가 표시되는가
- 샘플 모드가 아닌 입력으로 시험했는가
- OpenAI Usage에서 호출을 교차 확인했는가
- 민감정보 포함 입력을 사용하지 않았는가
- 키가 Git 변경 내역과 화면 캡처에 없는가
- API 장애 시 로컬 fallback과 고정 긴급 안내가 유지되는가

## 6. 공식 참고문서

- [OpenAI Developer quickstart](https://developers.openai.com/api/docs/quickstart)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Streamlit secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [Streamlit Community Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
