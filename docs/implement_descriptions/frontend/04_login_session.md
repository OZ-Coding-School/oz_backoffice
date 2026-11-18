# 04. FE-1a 로그인·세션 가드·비밀번호 재설정·가입 상태

- 상태: PR 진행 중
- 관련 PR: #76
- 관련 결정: `docs/decisions.md` F20~F22, A32·A33·A60·A61
- 이전 기록: [03. API 클라이언트](03_api_client.md)

## 배경
FE-1(인증 화면)을 BE-0(#75, 계정 종류) 다음 화면 PR 3개로 나눴다(F20). 이 PR은 그 첫 번째다.
- 앱 시작 시 세션 복원과 라우트 가드
- 수강생·멘토 로그인과 비밀번호 재설정
- 승인 전 회원의 가입 상태 모달
- 로그인 후 역할별 임시 홈

구현 전에 Figma에 반응형 뷰(모바일 390·태블릿 768)와 디자인에 없던 상태(세션 종료 안내, 멘토 재신청, 임시 홈)를 먼저 그렸다(F21).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `apps/backend/src/app/main.py`, `tests/api/test_cors.py` | CORS `expose_headers=["Retry-After"]`. 프론트(다른 출처)가 429의 남은 시간을 읽는다(F21) |
| `src/features/auth/api.ts` | `meQuery`·`memberSignupQuery`·`signupCohortsQuery`, `ensureSession`(앱을 연 뒤 한 번 refresh → `/me`), `login`, `logout` |
| `src/features/auth/guards.ts`, `navigation.ts` | `requireAccount`(아래 "라우트 가드" 참고), `afterLoginPath`(로그인 후 갈 곳) |
| `src/routes/_auth/login.tsx`, `password-reset.tsx`, `_member/index.tsx`(`/`), `_staff/admin.tsx`(`/admin`) | 파일 라우트. 로그인은 `?redirect`·`?email` 검색 파라미터 |
| `src/features/auth/components/auth-layout.tsx`, `brand.ts` | 소개 영역(데스크톱 560·태블릿 320·모바일 숨김 + 폼 위 로고), 소개 문구(F22), 오즈 워드마크 로고(F23) |
| `src/assets/brand/oz-wordmark-*.png`, `public/favicon.png`, `index.html` | 사용자가 준 오즈 로고: 워드마크(밝은 배경 다크 / 보라·다크 모드 라이트), 파비콘·홈 화면 아이콘은 원형 마크(F23) |
| `login-page.tsx` | 로그인 폼, 오류·잠금(Retry-After → "HH:mm부터")·세션 종료 Alert, 승인 전 회원이면 가입 상태 모달 |
| `password-reset-page.tsx` | 1단계(이메일) → 2단계(아래 참고) |
| `signup-status-dialog.tsx` | 승인 대기(신청 요약)·반려(사유, 수강생은 기수 / 멘토는 닉네임·보일 이름으로 재신청). 닫기는 로그아웃 |
| `temp-home.tsx` | 임시 홈(이름·역할 배지·로그아웃, F20) |
| `src/components/ui/` | `alert`, `dialog`, `radio-group`, `select`, `spinner`, `sonner`(Toaster)를 Figma `Components`에 맞춰 만들었다 |
| `src/components/form-field.tsx` | 라벨·도움말·오류 묶음, `InputIcon` |
| `src/components/pending-screen.tsx`, `src/router.tsx` | 0.3초 넘게 걸리면 스피너(F22) |
| `src/main.tsx` | 쓰는 중에 세션이 끝나면 로그인 화면으로 보낸다(F19·F20) |
| `src/api/errors.ts`, `client.ts`, `refresh.ts` | `ApiError.retryAfterSeconds`. 끝낼 세션이 없으면 refresh 401이 앞선 종료 사유를 덮지 않게 했다 |
| `src/lib/utils.ts` | tailwind-merge에 토큰 글자 스타일을 등록했다(아래 문제와 해결) |
| `src/lib/datetime.ts` | KST 표시 도우미(date-fns + @date-fns/tz) |
| `e2e/auth.spec.ts`, `e2e/home.spec.ts` | 로그인 → 새로고침 유지 → 로그아웃, 모바일·태블릿 소개 영역 |

**라우트 가드** (`requireAccount`)
- 로그인 안 함 → `/login?redirect=<경로>`
- 승인 전 회원 → `/login`(가입 상태 모달)
- 승인 전 운영진 → `/staff/registration`
- 다른 계정 종류의 영역 → 그 계정의 홈

**비밀번호 재설정 2단계** (`password-reset-page.tsx`)
- 코드 입력, 60초 재발송 카운트다운
- 비밀번호 규칙 체크(A30과 같은 판정), 비밀번호 확인
- 성공하면 Toast를 띄우고 로그인 화면에 이메일을 채운다.

**설치한 의존성 (정확한 버전):** sonner 2.0.8, react-hook-form 7.92.0, zod 4.6.7, @hookform/resolvers 7.0.7, date-fns 4.4.0, @date-fns/tz 1.5.0

## 주요 결정 (사용자 결정)
- **F20**
  - 로그인 후에는 역할별 임시 홈으로 보낸다.
  - 세션 종료는 로그인 폼 위 Alert로 알린다(탈취 Warning, 만료 Info, 계정 정지 Error, 처음 방문은 없음).
- **F21**
  - CORS에 `Retry-After`를 노출하는 설정을 이 PR에 담는다.
  - Toast는 sonner로 만든다.
  - 로그인 후에는 원래 가려던 화면으로 간다(같은 계정 영역일 때만).
  - 모든 화면은 반응형 3단계(390·768·1440)로 Figma에 먼저 그린 뒤 구현한다. 태블릿은 소개 영역 320을 둔다(사용자 제안).
- **F23 오즈 로고(사용자 제공 파일):** 워드마크 + 줄바꿈 + "운영 행정 지원 플랫폼"으로 하고, 파비콘은 원형 마크다. 기존 'OZ' 상자 마크는 쓰지 않는다.
- **F22**
  - 앱 시작 때는 빈 배경을 두고, 0.3초가 넘으면 스피너를 보여 준다.
  - 가입·운영진 로그인 링크는 디자인대로 둔다(화면은 FE-1b·1c).
  - 재설정 단계는 새로고침하면 1단계부터 다시 한다.
  - 소개 문구는 "수강부터 수료까지 / 필요한 지원을 한곳에서"이고, 회원 화면에는 기능 목록을 두지 않는다.

## 구현 세부
- **세션 복원은 앱을 연 뒤 한 번만 한다.** 로그인·로그아웃 뒤에는 메모리 세션을 그대로 쓴다.
- **로그인 후 갈 곳(`afterLoginPath`)**
  - `//`·외부 주소는 무시한다.
  - 회원은 `/admin`·`/staff/*`로, 운영진은 회원 경로로 보내지 않는다.
  - `/login`·`/password-reset`으로 가는 `redirect`도 홈으로 바꾼다.
- **로그아웃 표시:** 로그아웃은 `logged_out` 사유로 세션을 끝낸다. 로그인 화면 안내와 다른 탭 알림은 하지 않는다.
- **로그인 잠금:** 남은 시각이 지나면 Alert를 지우고 버튼을 다시 연다.
- **반려 재신청 결과**
  - 바로 승인되면 Toast "가입이 승인됐어요"를 띄우고 홈으로 간다.
  - 다시 대기면 승인 대기 모달로 바꾼다(A33, Figma 개발 메모).
- **jsdom 보완:** Radix 셀렉트·대화상자가 쓰는 `ResizeObserver`·`scrollIntoView`·포인터 캡처를 테스트 설정에 빈 함수로 두었다.
- **화면이 아직 없는 링크:** `/signup`·`/staff/login`은 화면이 없어 라우터 `Link` 대신 `<a>`로 두었다(FE-1b·1c에서 `Link`로 바꾼다).

## 발견한 문제와 해결
- **버튼 글자 색이 사라짐:** tailwind-merge가 `text-body-strong`(토큰 글자 크기)을 글자 색으로 보고 `text-primary-foreground`를 지웠다. Primary 버튼 글자가 검게 나왔다. `extendTailwindMerge`에 토큰 글자 스타일을 등록해 고쳤고 단위 테스트를 추가했다.
- **다크 모드 로고:** 소개 영역 로고의 "OZ"가 `primary-text`(다크에서 연보라)라 흰 배경 위에서 거의 보이지 않았다. 모드와 관계없는 `primary`로 바꿨다.
- **세션 종료 안내가 사라짐:** 세션이 끝난 뒤 로그인 화면이 refresh를 다시 시도하면, 401(`refresh_token_missing`)이 앞선 사유(`refresh_token_reused`)를 덮어 안내가 사라졌다. 끝낼 세션이 있을 때만 `endSession`을 부르게 했다.

## 검증
- **프론트엔드**
  - `lint`, `format:check`, `typecheck`, `build`: 통과(초기 JS 225kB, gzip 72kB)
  - `test`: 60 passed. 로그인·가드·가입 상태 14, 재설정 5, cn 2, Retry-After 1 추가
  - `e2e`: 7 passed
- **화면 확인:** `npm run dev` + API 모킹으로 세 크기(390·768·1440)를 캡처해 Figma와 비교했다(라이트, 다크 1440).
  - 로그인, 잠금, 재설정 2단계, 승인 대기, 반려(멘토), 임시 홈
- **백엔드 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 842 passed(CORS 테스트 2개 추가). 스키마 변경 없음(`openapi.json` 동일).

## 남은 작업
- FE-1b: 회원가입 마법사(`/signup`)
- FE-1c: 운영진 로그인(`?error=` 문구)·최초 정보 입력(`/staff/registration`), 운영진 소개 영역 기능 목록
- FE-2·FE-14: 임시 홈을 실제 회원·운영진 틀로 바꾼다
