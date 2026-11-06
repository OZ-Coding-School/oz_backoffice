# 11. Google OAuth 콜백을 백엔드가 받도록 변경

- 상태: 완료 (2026-11-06 병합)
- 관련 PR: #14
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P2-1
- 이전 기록: [08. P2-1 인증 기반과 운영진 Google 로그인](08_p2_1_auth_google_login.md) (이 기록의 콜백 방식을 바꾼다)

## 배경
08에서는 Google이 프론트 페이지로 code·state를 돌려보내고, 프론트 JS가 그 값을 `POST /auth/google/callback`으로 넘겼다. 이 방식은 SPA에서 흔히 쓰는 기본값으로 넣은 것이고 따로 결정받지 않았다. 사용자가 "왜 콜백을 프론트가 받냐"고 물었고, 비교한 뒤 백엔드가 받기로 했다(decisions A15).

이전 방식의 문제는 세 가지였다.
- code가 프론트 JS를 거친다.
- 프론트에 콜백 페이지가 필요하다.
- state가 Redis에만 있고 브라우저와 묶이지 않는다. 프론트가 따로 대조하지 않으면 로그인 CSRF가 가능하다. 공격자가 자기 code·state로 피해자를 자기 계정에 로그인시킬 수 있다.

## 구현 내용

| 경로 | 변경 |
| --- | --- |
| `identity/application/auth_service.py` | `start()`가 `LoginStart(authorization_url, state)`를 돌려준다. `complete()`는 `browser_state`(쿠키 값)를 받아 state와 상수 시간 비교한다. 다르면 code 교환 전에 `oauth_state_invalid` |
| `identity/presentation/router.py` | `GET /auth/google/authorize`(JSON)와 `POST /auth/google/callback`을 없앴다. 새로 둔 경로는 아래 둘이다 |
| | `GET /auth/google/login`: state 쿠키 `oz_oauth_state`(HttpOnly·Secure·SameSite=Lax·Path=`/api/v1/auth/google`·10분)를 설정하고 Google로 302 |
| | `GET /auth/google/callback`: 성공하면 refresh 쿠키 설정 + `{FRONTEND_BASE_URL}/`로 302. 실패(취소·state 불일치·Google 오류)하면 `{FRONTEND_BASE_URL}/login?error=<code>`로 302. 어느 쪽이든 state 쿠키를 지운다 |
| `core/config.py`, `.env.example` | `GOOGLE_REDIRECT_URI` 기본값을 백엔드 콜백(`http://localhost:8000/api/v1/auth/google/callback`)으로 바꾸고, `FRONTEND_BASE_URL`을 추가했다 |
| `tests/` | 로그인 리디렉션·state 쿠키 속성, 콜백 성공(리디렉션·refresh 쿠키·state 쿠키 삭제), 실패 리디렉션(다른 브라우저, 취소, Google 실패, 위조 state), 서비스의 브라우저 state 대조 |

## 주요 결정
- **사용자 결정 (A15):** 콜백은 백엔드가 받는다.
- 리디렉션 대상은 설정한 `FRONTEND_BASE_URL`로만 보낸다. 요청 파라미터로 받은 주소로는 보내지 않는다(오픈 리디렉트 방지). 로그인 후 원래 페이지로 돌아가는 기능이 필요하면 경로만 허용하는 방식으로 나중에 추가한다.
- state 쿠키는 SameSite=Lax다. Google에서 돌아오는 요청은 최상위 GET 이동이라 Lax 쿠키가 실린다.
- 콜백 실패는 JSON이 아니라 리디렉션으로 알린다(브라우저 이동이라서). Google 클라이언트 미설정은 개발 환경 설정 오류라 `/google/login`에서 503 JSON을 그대로 둔다.
- access 토큰은 로그인 직후에도 `/auth/refresh`로 받는다. 요청이 한 번 늘지만, 프론트는 access를 메모리에만 두므로 페이지를 열 때마다 어차피 refresh를 부른다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **188개 통과**(통합 포함)
- GitHub Actions (PR #14, run 42142316463): backend 잡 통과
- 사용자 확인: "백엔드가 받음" 선택에 따라 CI 통과 후 병합
- 실행 중인 api:
  - `/auth/google/login` → 302 Google 인가 URL, state 쿠키 속성 확인
  - `/auth/google/callback?error=access_denied` → 302 `/login?error=google_login_cancelled`

## 남은 작업
- 로컬 `.env`의 `GOOGLE_REDIRECT_URI`를 백엔드 콜백 URL로 바꾸고, 같은 값을 Google Cloud Console의 승인된 리디렉션 URI에 등록해야 한다. 그 뒤 실제 로그인을 확인한다.
- 배포 시 프론트(Vercel)와 API가 같은 사이트여야 refresh 쿠키(SameSite=Lax)가 갱신 요청에 실린다. 배포 도메인을 정할 때 확인한다.
