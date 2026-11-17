# 03. API 클라이언트 (OpenAPI 타입 생성, 인증·토큰 갱신)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` F6·F8·F19, A7·A60
- 이전 기록: [02. 디자인 토큰](02_design_tokens.md)

## 배경
초기 세팅 PR 3개(F8) 중 마지막이다. 화면 PR에서 백엔드 API를 타입 안전하게 부르고, 인증(access 토큰·refresh 쿠키 회전, A7)을 화면 코드가 신경 쓰지 않도록 클라이언트에서 처리한다. 설계 중에 탭 여러 개가 동시에 갱신하면 refresh 재사용으로 판정돼 전체 로그아웃되는 문제를 찾았다. 그래서 백엔드에 유예 시간을 먼저 넣었고(#73, A60), 이 PR에서 프론트 탭 간 잠금을 넣는다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `apps/backend/src/app/cli.py` | `python -m app.cli export-openapi`. 서버·DB 없이 `create_app().openapi()`를 JSON으로 출력한다 |
| `apps/frontend/openapi.json` | 백엔드가 내보낸 스키마(커밋, 경로 145개) |
| `apps/frontend/tools/openapi/` | openapi-typescript 7.13.0 + TypeScript 5.9.3 전용 package.json·잠금 파일 |
| `apps/frontend/src/api/schema.gen.ts` | `npm run api:gen`이 만든 타입(커밋) |
| `src/api/client.ts` | `api`(openapi-fetch) + 인증 미들웨어(토큰 첨부, 만료 30초 전 미리 갱신, 401이면 한 번 갱신 후 재시도), `unwrap()` |
| `src/api/refresh.ts` | 갱신. 탭 안 동시 요청은 하나로 모으고, 탭끼리는 Web Locks(`oz-auth-refresh`)로 한 번에 하나씩. 401이면 세션 종료, 5xx·네트워크 오류는 세션 유지 |
| `src/api/session.ts` | Zustand 세션(access 토큰·만료·끝난 사유). 세션 종료 구독, BroadcastChannel(`oz-auth`)로 다른 탭과 함께 로그아웃 |
| `src/api/errors.ts` | `ApiError`. 백엔드 오류 `{"error": {code, message}}`와 422 `{"detail": [...]}`(필드별 메시지)를 한 형태로, 재시도 판정 |
| `src/lib/query-client.ts` | 조회 재시도: 네트워크 오류·5xx만 1회 |
| `src/main.tsx` | 세션이 끝나면 Query 캐시를 비운다 |
| `src/mocks/api.ts` | MSW용 `apiUrl()`(생성 타입 경로만 허용, `{id}` → `:id`), `errorBody()` |
| `.github/workflows/ci.yml` | 아래 "CI 검사" 참고 |
| `apps/frontend/CLAUDE.md` | 명령어(`api:schema`·`api:gen`), 구조, API 호출 규칙 |

**CI 검사** (`.github/workflows/ci.yml`)
- 백엔드 잡: 스키마를 다시 내보내 커밋된 `openapi.json`과 비교한다.
- 프론트 잡: 타입을 다시 만들어 커밋된 `schema.gen.ts`와 비교한다.
- `openapi.json`만 바뀌어도 백엔드 잡이 돌도록 경로 필터에 추가했다.

**설치한 의존성 (정확한 버전):** openapi-fetch 0.17.0, zustand 5.1.0 (앱), openapi-typescript 7.13.0·typescript 5.9.3 (`tools/openapi`)

## 주요 결정 (사용자 결정, F19)
- **타입 생성과 CI 검사**
  - API 타입은 백엔드 내보내기 파일에서 만든다.
  - CI는 스키마와 생성 타입을 둘 다 검사한다.
  - 내보내기 명령·CI·클라이언트는 한 PR에 담는다.
- **토큰 갱신**
  - 만료 30초 전이면 요청 전에 미리 갱신하고, 그래도 401이면 한 번 더 갱신한다.
  - 탭 간 잠금(Web Locks)을 걸고, 백엔드 유예 시간(A60)도 함께 둔다.
- **세션 종료:** 세션이 끝나면 access 토큰과 Query 캐시를 비우고, 사유 코드를 남기고, 다른 탭에 알린다.
- **재시도:** 조회 재시도는 네트워크 오류·5xx만 1회 한다.
- **생성 도구 분리:** openapi-typescript는 TypeScript 5를 peer 의존성으로 요구한다. 앱 의존성(TypeScript 7)에 강제로 넣으면 실행이 실패했다. 그래서 `tools/openapi/`에 따로 둔다(사용자 결정).

## 구현 세부
- **경로는 `/api/v1/...` 전체를 쓴다.** 생성 타입의 경로가 `/api/v1/...`이라 `baseUrl`은 백엔드 주소(`VITE_BACKEND_URL`)다.
- **401 재시도:** 보내기 전 요청을 복제해 두었다가 401이면 새 토큰으로 다시 보낸다. 본문이 있는 요청도 같은 본문으로 다시 보낸다.
- **재시도하지 않는 경우**
  - 로그인하지 않은 상태(토큰 없음)의 401
  - `/api/v1/auth/*`(로그인·갱신·가입) 요청
  - 재시도 뒤에도 401인 경우(더 갱신하지 않음)
- **MSW 호환:** openapi-fetch는 만들 때 `fetch`를 잡아 둔다. MSW가 바꾼 전역 `fetch`를 쓰도록 호출할 때마다 `globalThis.fetch`를 찾게 했다.
- **세션이 없던 탭:** 다른 탭에 로그아웃을 알리는 것은 이 탭에 세션이 있었을 때만 한다. 로그인하지 않은 방문자의 갱신 실패가 다른 탭을 건드리지 않게 하기 위해서다.
- **Web Locks를 지원하지 않는 환경**(jsdom 등)에서는 탭 안에서만 갱신 요청을 하나로 모은다.
- **브라우저 저장소:** access 토큰은 메모리(Zustand)에만 두고 브라우저 저장소에 쓰지 않는다(A7).

## 발견한 문제와 해결
- **openapi-typescript와 TypeScript 7:** peer `typescript@^5`. 앱에 `--legacy-peer-deps`로 넣으면 TypeScript 7에서 생성이 실패한다(별도 폴더에서 확인). 그래서 TypeScript 5와 함께 별도 도구 패키지로 분리했다.
- **스키마가 환경에 따라 달라지는지:** `.env` 없이 호스트에서 `uv run`으로 내보낸 결과가 컨테이너 결과와 바이트 단위로 같았다. CI(환경 변수 없음)에서도 같은 결과가 나온다.

## 검증
- **백엔드 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 839 passed(내보내기 테스트 2개 추가).
- **프론트엔드**
  - `lint`, `format:check`, `typecheck`, `build`: 통과
  - `npm test`: 40 passed (클라이언트 인증 10, 오류 변환 4, 세션 3, Query 재시도 2 추가)
  - `e2e`: 5 passed
  - `npm run api:gen`을 다시 실행해도 `schema.gen.ts`가 바뀌지 않는다.
- **클라이언트 인증 테스트 내용**
  - 토큰 첨부, 만료 30초 전 미리 갱신, 401 → 갱신 → 재시도
  - 동시 401 3건에 갱신 1회
  - 재시도 후 401이면 멈춤, 비로그인은 갱신하지 않음
  - 갱신 401이면 세션 종료와 사유, 갱신 5xx면 세션 유지
  - Web Locks 사용, 본문 있는 요청 재전송

## 남은 작업
- FE-1a: 앱 시작 시 refresh → `/me`, 역할별 진입·승인 게이트, `endedReason`을 보고 로그인 화면 안내
- FE-7: 채팅 SSE도 같은 갱신 함수로 토큰을 갱신하고 다시 연결한다
