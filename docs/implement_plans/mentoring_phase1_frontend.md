# 멘토링 1단계 프론트엔드 상세 구현계획

- 작성일: 2026-11-17
- 상태: 계획 확정, 초기 세팅 ①(#66) 완료
- 범위: 멘토링 1단계의 프론트엔드(`apps/frontend`). 화면은 Figma 디자인을 기준으로 하고, 설계 중에 나온 백엔드 보완 API도 이 계획에서 순서를 정한다.
- 기준 문서: `docs/decisions.md`(결정, 특히 F1~F17), `docs/implement_plans/mentoring_phase1_backend.md`(API·권한표), `apps/frontend/CLAUDE.md`(작업 하네스), Figma 파일(페이지 `Design System`·`Components`·`Login`·`Member - 수강생`·`Member - 멘토`·`Admin - *`)

---

## 0. 범위

### 포함
- 초기 세팅 ② 디자인 토큰 ③ API 클라이언트 (F8)
- 로그인·가입: 수강생·멘토 로그인, 회원가입 마법사, 비밀번호 재설정, 가입 상태(승인 대기·반려·재신청), 운영진 Google 로그인, 운영진 최초 정보 입력 (F10·F11)
- 수강생 화면: 홈, 멘토링 신청, 신청 내역·상세·변경·취소, 진행 기록·세션 상세(녹화·전사·스마트 메모), 내 팀, 채팅, 시간 지급·차감 내역, 내 정보 (F12~F14)
- 멘토 화면: 홈, 받은 신청·상세·승인·반려, 세션·기록 작성, 일정(불가 시간·신청 받기), 채팅, 정산, 내 프로필 (F12·F14)
- 운영진 화면: 공통 틀(모듈 레일·메뉴·현재 기수), 홈, 회원·권한, 설정(조직·공휴일), 학사, 강사·멘토, 멘토링 관리 7개 메뉴 (F3)
- 반응형(F21): 모든 화면을 모바일 390 · 태블릿 768 · 데스크톱 1440으로 만든다. Figma에 크기별 뷰가 없으면 그 PR을 시작할 때 먼저 그린다

### 제외 (F15: 이번 범위가 아닌 화면 구성은 구현하지 않는다)
디자인에 아래 요소가 있어도 **메뉴·탭·카드·링크까지 넣지 않고** 범위 안 요소만 구현한다. 백엔드가 생기면 그때 계획에 추가한다.

| 항목 | 디자인 위치 | 이유 |
| --- | --- | --- |
| 헬프센터(신청서·출결 확인·FAQ·문의) | 수강생·멘토 사이드바, 홈 모듈 카드, 모바일 탭 | 후속 단계 (D2) |
| 내 문서함(서류 서명 내역) | 수강생 사이드바 | 후속 단계 |
| 운영진 모듈: 출결 감시, 행정 업무, 디스코드 관리 | `Admin - 출결 감시`·`행정 업무`·`디스코드 관리` | 백엔드 없음 |
| 운영진 학사 > 수강생 상세의 출결·행정 탭 | `Admin - 학사 관리` | 백엔드 없음 |
| 운영진 설정 > 외부 연동·발송·작업 현황·감사 로그 | `Admin - 설정` | 조회 API 없음 |
| 알림(상단 막대 알림 버튼, 운영진 알림 화면, 홈 알림 영역) | 공통 | 알림 방식 보류 (M24) |
| 운영진 강사 화면 | `Admin - 강사·멘토 관리` | 강사 관리 API 없음 (계약 화면의 강사 계약은 포함) |
| 비밀번호 변경(로그인 상태) | 내 정보 | API 없음, 비밀번호 재설정으로 안내 (디자인 그대로) |

---

## 1. 적용되는 주요 결정 (요약)

| 영역 | 결정 | 번호 |
| --- | --- | --- |
| 스택 | React·Vite·TS·Tailwind·shadcn/ui·TanStack Router/Query·Zustand·lucide, oxlint·Prettier, Vitest·Testing Library·MSW·Playwright | F1, F5, F9 |
| 상태 | 서버 데이터는 TanStack Query, 클라이언트 전용 상태만 Zustand. 목록 필터·페이지는 검색 파라미터 | F2, F5 |
| API 타입 | OpenAPI에서 생성(openapi-typescript + openapi-fetch), 생성 파일 커밋 | F6 |
| 토큰 | access는 메모리, refresh는 HttpOnly 쿠키(회전) | A7 |
| 운영진 로그인 | 브라우저를 `/auth/google/login`으로 보내고, 백엔드 콜백이 `{FRONTEND}/` 또는 `/login?error=`로 돌려보냄 → 프론트는 `/auth/refresh` | A15 |
| 마크다운 | 신청 상세·기록 요약·세션의 신청 정보는 GFM, 이미지·HTML 불가, 링크 새 창 | F4 |
| 라이브러리 | React Hook Form + Zod, date-fns + @date-fns/tz, react-markdown + remark-gfm + Shiki, SSE는 fetch 스트림 직접 구현 | F16 |
| 채팅 | REST 전송 + SSE 수신(사용자당 연결 하나), 끊기면 다시 조회, 운영진은 열람만 | A57, A58 |
| 메뉴 권한 | 백엔드가 유효 권한 코드·범위를 내려주고 프론트는 숨김만, 최종 판정은 서버 | F3, F17 |
| 화면 구조 | 운영진: 모듈 레일 + 모듈 메뉴 + 현재 기수. 회원: 사이드바 + 모듈 그룹, 모바일 하단 탭 | F3, F12 |
| 용어 | 시간 보류(HOLD)는 화면에서 '차감 예정' | F14 |
| 순서 | 로그인 → 수강생 → 멘토 → 운영진, 보완 API는 해당 화면 PR 바로 앞 | F15 |

---

## 2. 공통 규약

### 2.1 경로 (라우트)
경로 이름은 아래를 기본으로 하고, 각 PR에서 바꿀 필요가 생기면 사용자에게 확인한다.

| 영역 | 경로 |
| --- | --- |
| 인증 | `/login`, `/signup`, `/password-reset`, `/staff/login`, `/staff/registration`(A61) |
| 수강생 | `/`(홈), `/mentoring/apply`, `/mentoring/requests`, `/mentoring/requests/$id`, `/mentoring/requests/$id/edit`, `/mentoring/sessions`, `/mentoring/sessions/$id`, `/mentoring/team`, `/mentoring/chat`, `/mentoring/balance`, `/me` |
| 멘토 | `/`(홈), `/mentor/requests`, `/mentor/requests/$id`, `/mentor/sessions`, `/mentor/sessions/$id`, `/mentor/schedule`, `/mentor/chat`, `/mentor/settlements`, `/mentor/settlements/$id`, `/mentor/profile` |
| 운영진 | `/admin`(홈), `/admin/<모듈>/<메뉴>` (예: `/admin/mentoring/requests`, `/admin/academy/cohorts`) |

- 로그인 후 진입: 역할이 STUDENT면 수강생, MENTOR면 멘토, 운영진 역할이면 `/admin`. 역할에 맞지 않는 경로는 그 사용자의 홈으로 보낸다.
- 회원의 기수 선택(상단 막대)과 운영진의 현재 기수는 검색 파라미터가 아니라 Zustand(+ localStorage 기억)로 두고, 기수 단위 API의 `cohort_id`에 쓴다.

### 2.2 인증과 세션
- **access 토큰은 메모리(Zustand, 저장하지 않음)**. 앱을 열면 `POST /auth/refresh`(쿠키, `credentials: "include"`)로 access를 받고 `GET /me`로 사용자를 불러온다. 실패하면 로그인 화면으로 보낸다.
- API 클라이언트 미들웨어가 `Authorization: Bearer`를 붙인다. **401이면 refresh를 한 번만**(동시 요청은 하나의 갱신을 기다림) 하고 원래 요청을 다시 보낸다. 갱신이 실패하면 세션을 지우고 로그인으로 보낸다.
- **승인 게이트:** `approval_status`가 APPROVED가 아니면 가입 상태 화면(승인 대기·반려 모달, `/me/member-signup` 재신청, 운영진은 `/staff/registration`)만 쓸 수 있다.
- 로그아웃은 `POST /auth/logout` 뒤 Query 캐시와 세션을 비운다.
- 운영진 로그인: `?error=<code>` 문구는 Figma `Login / Notes`의 표를 따른다.

### 2.3 API 클라이언트와 오류
- 생성 타입(`src/api/schema.gen.ts`)과 `openapi-fetch` 클라이언트 하나를 쓴다. 생성 스크립트는 `npm run api:gen`(백엔드 OpenAPI → 타입)이고, 백엔드 API가 바뀌면 다시 만들어 커밋한다.
- 오류 응답 `{"error": {"code", "message"}}`을 `ApiError(code, status, message)`로 바꾼다. 화면 문구는 **오류 코드 → 문구 표**를 기능별로 두고(예: `invalid_credentials`, `login_locked`, `insufficient_balance`), 표에 없는 코드는 서버 message를 보여 준다. 422는 폼 필드 오류로 연결한다.
- Query 키는 기능별 팩토리(`requestKeys.list(filters)` 등)로 만들고, 뮤테이션 뒤에는 관련 키를 무효화한다.
- 쓰기 요청에 `Idempotency-Key`가 필요한 API(시간 지급 등, A40)는 폼을 열 때 키를 만들고 다시 시도할 때 같은 키를 쓴다.

### 2.4 목록·페이지
- `limit`/`offset` 목록은 검색 파라미터(`page`, 필터)로 두고 표·카드 목록에 같은 페이지네이션 컴포넌트를 쓴다.
- 커서 목록(채팅 메시지, 원장)은 `useInfiniteQuery`로 이전 페이지를 이어 붙인다.

### 2.5 날짜·시간
- 서버는 UTC ISO 8601을 주고받는다. 화면 표시와 입력은 **Asia/Seoul**(date-fns + @date-fns/tz)로 하고, 보낼 때 오프셋이 붙은 ISO로 바꾼다.
- 신청 가능 시간·불가 시간은 30분 경계, 진행 시간은 기수의 진행 단위 배수(최대 120분)를 폼에서 먼저 검사하고 최종 판정은 서버에 맡긴다.
- 표기 형식은 Figma를 따른다(예: `11/24(화) 19:00`, 시간은 고정폭 글꼴).

### 2.6 마크다운·파일
- 마크다운은 공용 `<Markdown>` 컴포넌트 하나로 보여 준다(HTML 렌더링 안 함, `img`는 링크 텍스트로 바꿈, 링크는 `target=_blank rel=noopener noreferrer`, 코드 블록은 Shiki 지연 로드).
- 작성 화면(신청 내용, 기록 요약)은 작성란과 미리보기를 나란히 두고 같은 컴포넌트로 미리보기한다. 글자 수는 원문 기준.
- 업로드(계약서, 멘토 사진)는 presigned POST → S3 → confirm 순서의 공용 훅 하나로 처리한다. 멘토 사진은 브라우저에서 줄여 올린다(A28).

### 2.7 디자인 시스템
- Figma 변수(라이트·다크)를 Tailwind·shadcn CSS 변수로 옮기고, 텍스트 스타일(Display, Heading/H1~H3, Body/*, Caption, Label)을 유틸리티로 만든다. 글꼴은 Noto Sans KR과 Fira Code.
- 컴포넌트는 shadcn/ui를 기본으로 Figma `Components` 페이지에 맞춰 고친다(Button·Badge·Input·Textarea·Radio·Avatar·Breadcrumb·Tabs·Dialog·Table 등). 화면 전용 조각은 기능 폴더에 둔다.
- 상태 색 규칙(F14): 상태는 배지·띠·배경색으로만 표시하고 텍스트에는 상태 색을 쓰지 않는다.

### 2.8 구조
```text
src/
├── api/            # schema.gen.ts(생성), client.ts(openapi-fetch + 인증 미들웨어), errors.ts
├── components/ui/  # shadcn 컴포넌트 (Figma에 맞춘 것)
├── components/     # 앱 공통 조각 (Markdown, Pagination, EmptyState, Upload …)
├── features/<기능>/ # api.ts(쿼리·뮤테이션 훅, 키), components/, schemas.ts(Zod), messages.ts(오류 문구)
├── layouts/        # 회원·운영진 틀(사이드바·상단 막대·탭 바)
├── routes/         # 파일 기반 라우트 (화면 조립만, 로직은 features)
├── stores/         # Zustand (session, cohort, ui)
└── mocks/handlers/ # 기능별 MSW 핸들러 (생성 타입 사용)
```

### 2.9 테스트
- 각 화면 PR: 주요 상호작용 컴포넌트 테스트(Testing Library + MSW, 성공·대표 오류 코드), 핵심 흐름 E2E 1~2개(`page.route`로 API 모킹).
- 인증 미들웨어(401 → 갱신 → 재시도, 동시 요청 하나의 갱신), SSE 파서, 날짜 변환은 단위 테스트를 둔다.
- 완료 기준은 `apps/frontend/CLAUDE.md`의 검사(`lint`, `format:check`, `typecheck`, `test`, `build`, `e2e`) 통과와 구현 기록.

---

## 3. 백엔드 보완 API

화면 PR 바로 앞에 백엔드 PR로 만든다(F15). 각 PR의 세부 규칙은 그 PR을 시작할 때 사용자에게 확인하고 `decisions.md`에 추가한다.

| PR | 내용 | 필요한 화면 | 근거 |
| --- | --- | --- | --- |
| BE-0 | 인증 화면 보완: `users.account_type`(MEMBER/STAFF)과 `/me` 응답, Google 로그인 실패 경로 `/staff/login?error=` (A61) | FE-1 | F20 |
| BE-1 | 수강생 멘토링 신청 준비: **내 수강 등록 목록**(기수·기간·상태), **기수 멘토링 설정 요약**(허용 종류 1:1·팀, 진행 단위, 신청 마감 등), **신청 받는 멘토 목록·공개 프로필**(`GET /me/mentoring/mentors?cohort_id`, 표시 이름·사진·headline·expertise·introduction, 실명·연락처 제외) | FE-2(기수 선택), FE-3(신청), 내 정보 | F12, F13 |
| BE-1b | 신청 응답 보완: **신청 단건 조회**, 응답에 **확정 세션**·**멘토 한 줄 소개**·**취소 주체**·**차감 상태** (A66) | FE-4a(신청 내역 목록·상세·취소) | F14·F28 |
| BE-1c | 신청 목록: **상태 여러 개 필터**, 응답에 **상태별 건수** `counts`(수강생·멘토 목록, A67) | FE-4a 탭(전체·승인 대기·승인·반려·취소) | F29 |
| BE-2 | 수강생 세션 보완: 세션 응답에 **실제 진행 시각**(Meet)·**참여자 목록**, 세션 상세의 **전사본 텍스트**(옆 패널용) 제공 방식, 녹화 영상 재생 인증 방식(아래 리스크) | FE-5(진행 기록·세션 상세), FE-10 | F14 |
| BE-3 | 운영진 **유효 권한 코드·범위** 응답 | FE-14(운영진 틀) | F17 |
| BE-4 | (필요 시) 운영진 홈·멘토링 대시보드 집계 | FE-14, FE-23 | F3 — 기존 목록 API 조합으로 충분한지 그 PR에서 판단 |

---

## 4. PR 계획

순서는 의존 관계와 F15의 순서를 따른다. PR이 크면 기능 단위로 더 나눈다(예: FE-3a/3b). 각 PR은 해당 Figma 화면을 구현하고, 범위 밖 요소는 빼고(F15) 구현 기록을 남긴다.

```text
FE-0a 디자인 토큰 ─ FE-0b API 클라이언트 ─ FE-1 인증·로그인·가입
 ─ BE-1 ─ FE-2 회원 틀 ─ FE-3 신청 ─ FE-4 신청 내역 ─ BE-2 ─ FE-5 진행 기록 ─ FE-6 팀·시간·내 정보 ─ FE-7 채팅 ─ FE-8 수강생 홈
 ─ FE-9 받은 신청 ─ FE-10 세션·기록 ─ FE-11 일정 ─ FE-12 정산·프로필 ─ FE-13 멘토 홈
 ─ (운영진 Figma 마무리) ─ BE-3 ─ FE-14 운영진 틀·홈 ─ FE-15 회원·권한 ─ FE-16 설정 ─ FE-17 학사 ─ FE-18 강사·멘토
 ─ FE-19 멘토링 설정·팀 ─ FE-20 멘티 ─ FE-21 신청·세션 관리 ─ FE-22 정산 관리 ─ (BE-4) ─ FE-23 멘토링 대시보드
```

### FE-0. 초기 세팅 ②③ (F8)
- **FE-0a 디자인 토큰:** Tailwind·shadcn 설치, Figma 라이트·다크 변수 → CSS 변수, 텍스트 스타일, 폰트, 다크 모드 전환(시스템 따름 + 수동, localStorage), 기본 컴포넌트 몇 개(Button·Badge·Input)와 확인용 화면.
- **FE-0b API 클라이언트:** `api:gen` 스크립트와 생성 타입, openapi-fetch 클라이언트, 인증 미들웨어(2.2), `ApiError`, Query 키 규칙, 세션 스토어, 생성 타입을 쓰는 MSW 핸들러 도우미.

### FE-1. 인증·로그인·가입 (Figma `Login`)

> F20으로 PR을 다시 나눴다: BE-0 → FE-1a(앱 시작·가드 + 로그인·재설정·가입 상태 모달) → FE-1b(가입 마법사) → FE-1c(운영진 로그인·정보 입력). 아래 항목 구분은 화면 묶음 설명으로 둔다. 로그인 후에는 역할별 임시 홈으로 보낸다(FE-2·FE-14에서 교체).
- **FE-1a 앱 시작·가드:** 시작 시 refresh → `/me`, 역할별 진입, 승인 게이트, 로그아웃.
- **FE-1b 수강생·멘토 로그인·비밀번호 재설정:** `POST /auth/login`(401·429 잠금 안내), `/auth/password-reset/code`·`/auth/password-reset`, 가입 상태 모달(`GET/POST /me/member-signup`, 대기·반려·재신청).
- **FE-1c 회원가입 마법사 (F10):** 유형 → 이메일 인증 → 휴대폰 인증 → 가입 정보(수강생은 `GET /auth/signup/cohorts`) → 완료(대기·승인). 오류 화면(409·429·코드 불일치·가입 토큰 만료).
- **FE-1d 운영진:** Google 로그인 버튼·`?error=` 안내, 최초 정보 입력(`/me/staff-registration/options`, `GET/PUT /me/staff-registration`, 대기·반려 단독 화면, F11).

### FE-2. 회원 공통 틀 (BE-1 이후)
- 수강생·멘토 사이드바(모듈 그룹, 헬프센터·내 문서함 제외), 상단 막대(위치·기수 선택·테마), 모바일 하단 탭(홈·멘토링·내 정보, 헬프센터·알림 제외), 빈 상태·로딩·오류 공통 조각. 홈은 FE-8·FE-13에서 채운다.

### FE-3. 수강생 멘토링 신청 (F13)
- 종류 선택(둘 다 허용일 때), 팀 멘토 확인 / 1:1 멘토 선택(신청 받는 멘토만, 상세 소개 모달), 일정 선택(`GET /mentors/{id}/available-times`, 진행 시간·희망 일시 1~3), 신청 내용(작성·미리보기 나란히), 신청 확인(단계별 수정), 완료. `POST /mentoring/requests`.
- 단계 상태는 라우트 검색 파라미터 + 폼 상태로 두고, 새로 고침해도 이전 단계 값이 남도록 sessionStorage에 임시 저장한다.

### FE-4. 수강생 신청 내역 (F14)
- 카드 목록(`GET /me/mentoring/requests`, 상태 필터), 신청 상세 페이지, 취소 확인(`POST …/cancel`), 변경 페이지(`POST …/change`, 같은 멘토·종류, 일정·내용 한 페이지).

### FE-5. 진행 기록·세션 상세 (BE-2 이후, F14)
- 카드 목록(`GET /me/mentoring/sessions`), 세션 상세(`GET /mentoring/sessions/{id}`), 녹화 영상과 옆 패널(전사·스마트 메모 탭, `GET …/artifacts`·`…/content`), 기록 요약 마크다운.

### FE-6. 내 팀·시간 지급·차감 내역·내 정보
- 내 팀(`GET /me/mentoring-teams`, 팀 멘토링 허용 기수에서만 메뉴 표시), 시간 지급·차감 내역(`GET /me/balances`, `…/{id}/transactions` 커서, '차감 예정' 표기), 내 정보(`GET /me` + 수강 등록, 비밀번호 재설정 안내).

### FE-7. 채팅 (수강생·멘토 공통)
- 방 목록(`GET /me/mentoring/chat/threads`, 안 읽음 수), 메시지(커서 `before`, 위로 불러오기), 보내기(`POST /mentoring/chat/messages` 첫 메시지 / `…/threads/{id}/messages`), 삭제, 읽음(`PUT …/read`), 안내 메시지 표시.
- SSE(`GET /me/mentoring/chat/stream`): fetch 스트림 파서, 로그인한 동안 연결 하나, 토큰 갱신·끊김 시 다시 연결하고 목록·열린 방을 다시 조회(A58). 받은 이벤트는 Query 캐시에 반영한다.

### FE-8. 수강생 홈
- 할 일 요약(대기 신청, 다가오는 세션, 안 읽은 채팅, 잔여 시간)과 멘토링 모듈 카드. 헬프센터 카드는 제외.

### FE-9. 멘토 받은 신청
- 목록(`GET /me/mentor-requests`, 상태 필터), 신청 상세 페이지(희망 일시 골라 승인 `POST …/approve {starts_at}`, 겹치는 일시 비활성), 반려 확인 창(`POST …/reject {reason}`).

### FE-10. 멘토 세션·기록
- 세션 목록(`GET /me/mentor-sessions`, 기록 미제출 표시), 세션 상세, 기록 작성·수정(`POST/PATCH …/record`, 완료·노쇼, 30분 단위 실제 진행 시간, 요약 마크다운, 7일 수정), 내부 메모(`GET/PUT …/note`), 녹화·전사.

### FE-11. 멘토 일정
- 주간 보기(불가 시간·내 세션·운영시간 밖), 신청 받기 스위치(`PUT /me/mentor-schedule/accepting`), 불가 시간 추가·수정·삭제(한 번·매일·매주, 30분 경계, 자정 넘김), 대기 신청 충돌 확인(A45, 응답 형식은 PR에서 확인).

### FE-12. 멘토 정산·내 프로필
- 정산 목록·상세(`GET /me/mentor-settlements`, 마감된 것만), 내 프로필(`GET/PATCH /me/mentor-profile`, 사진 업로드·삭제, 배정 기수 `GET /me/mentor-assignments`).

### FE-13. 멘토 홈
- 처리할 신청, 오늘·다가오는 세션, 기록 미제출, 안 읽은 채팅, 신청 받기 상태. 헬프센터 카드는 제외.

### 운영진 화면 (Figma 초안을 다듬은 뒤 착수, F15)
권한은 BE-3 응답으로 숨기고, 기수 단위 화면은 상단 막대의 현재 기수를 쓴다. 신청 상세는 모달(F4), 세션 상세는 페이지(F3).

| PR | 화면 | 주요 API |
| --- | --- | --- |
| FE-14 | 운영진 틀(모듈 레일·메뉴·현재 기수·권한 숨김, 범위 밖 모듈 제외), 홈(처리할 일 요약) | BE-3, 기존 목록 API(가입 승인 대기, 운영진 승인 대기, 기록 미제출 등) |
| FE-15 | 회원 관리·조직 설정 (F64로 개편): 회원 관리 모듈(가입 승인 — 탭 3개: 수강생 · 멘토·강사 · 직원, 전체 회원 — 조회·비활성화), 조직 설정 모듈(부서·직위·직원·권한) | `/admin/approvals*`, `/admin/staff-registrations*`, `/admin/employees*`, `/admin/departments`·`/admin/teams`, `/admin/positions`(권한·데이터 범위), `/admin/users*`(새) |
| FE-16 | 설정: 공휴일 (조직·직위는 FE-15 조직 설정 모듈로 옮김, F64) | `/admin/mentoring-holidays` |
| FE-17 | 학사: 과정·기수, HRD 과정·회차, 수강생 명단·상세(기본·수강·멘토링 요약), 명단 동기화(실행·이력·매핑 실패) | `/admin/bootcamps*`, `/admin/cohorts*`, `/admin/hrd-*`, `/admin/rosters*` |
| FE-18 | 강사·멘토: 멘토 목록·프로필 대리 수정·활성화/비활성화·일정 대리, 계약(업로드·확정·해지·연결·파일 보기), 기수 배정 | `/admin/mentors*`, `/admin/contracts*`, `/admin/contract-files/uploads*`, `/admin/cohorts/{id}/mentor-assignments*` |
| FE-19 | 멘토링 설정(기본 규칙·운영시간·금지 시간대·휴일 한 페이지), 팀 관리·팀 상세(팀원·팀 시간 계좌·팀 채팅 열람·신청·세션) | `…/mentoring-settings`, `…/mentoring-block-times`, `…/mentoring-teams*`, `…/mentoring-balances*`, `…/mentoring/chat/threads?team_id` |
| FE-20 | 멘티 관리(목록·일괄 지급)·멘티 상세(시간 계좌 원장·지급·조정·기간 수정, 신청·세션, 1:1 채팅 열람) | `…/mentoring/mentees`, `…/mentoring-balances*`, `…/mentoring/requests?student_id`, `…/sessions?student_id`, `…/chat/threads?student_id` |
| FE-21 | 신청 관리(목록·상세 모달·운영진 취소), 세션 관리·세션 상세 페이지(기록·내부 메모·녹화·미제출) | `…/mentoring/requests*`, `…/mentoring/sessions*`, `…/sessions/unrecorded` |
| FE-22 | 정산 관리(집계·목록·상세·마감·CSV) | `…/mentoring/settlements*` |
| FE-23 | 멘토링 대시보드 | 기존 API 조합 또는 BE-4 |

---

## 5. 선행 준비물

| 준비물 | 필요한 PR | 상태 |
| --- | --- | --- |
| Figma 수강생·멘토 화면 | FE-1~FE-13 | 완료 (F10~F14) |
| Figma 운영진 화면 다듬기 (`Admin - *` 초안) | FE-14~FE-23 | 초안 |
| 프론트·API 같은 사이트 도메인 (refresh 쿠키 SameSite=Lax) | 배포(Vercel, R4) | 미정 — `docs/operations/production_notes.md` |
| 백엔드 `CORS_ORIGINS`·`FRONTEND_BASE_URL`에 프론트 주소 | FE-1 로컬 확인 | 로컬 기본값(5173) 확인 |

## 6. 리스크

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| 녹화 영상 중계가 `Authorization` 헤더를 요구 | `<video src>`는 헤더를 보낼 수 없어 재생 불가 | BE-2에서 재생 방식(짧은 서명 URL 등)을 정한다 |
| 전사본·스마트 메모가 PDF로만 중계됨(A54) | 옆 패널에 텍스트로 보여 줄 수 없음 | BE-2에서 텍스트 제공 방식을 정하거나 PDF 보기로 대체 |
| refresh 쿠키가 다른 사이트에서 안 실림 | 운영 배포 후 로그인 유지 실패 | 프론트·API를 같은 사이트 도메인으로 배포 |
| OpenAPI 타입과 실제 응답 불일치 | 런타임 오류 | 백엔드 API 변경 PR마다 `api:gen`, CI typecheck로 확인 |
| 디자인 범위 밖 요소가 섞임 | 범위 확장·빈 화면 | F15 제외표를 PR 체크리스트에서 확인 |
| 채팅 SSE 끊김·중복 | 메시지 누락 | 다시 연결 시 다시 조회, 메시지 ID로 캐시 중복 제거 |

## 7. 진행 체크리스트

- [x] 초기 세팅 ① 도구·테스트 구성 (#66, 구현 기록 frontend/01)
- [x] FE-0a 디자인 토큰 (#72, 구현 기록 frontend/02, F18)
- [x] FE-0b API 클라이언트 (#74, 구현 기록 frontend/03, F19)
- [x] BE-0 계정 종류·운영진 로그인 실패 경로 (#75, 구현 기록 backend/59, A61)
- [x] FE-1 인증·로그인·가입 (F20: 1a 앱 시작·가드·로그인·재설정·가입 상태, 1b 가입 마법사, 1c 운영진)
- [x] BE-1 수강생 신청 준비 API
- [x] FE-2 회원 공통 틀
- [x] BE-1b 신청 응답 보완 (#84, 구현 기록 backend/64, A66)
- [x] BE-1c 신청 목록 상태 필터·건수 (#85, 구현 기록 backend/65, A67)
- [x] FE-3 수강생 멘토링 신청 (3a 1:1: #87, 구현 기록 frontend/09, F30 / 3b 팀·종류 선택: #88, 구현 기록 frontend/10, F31)
- [x] FE-4 수강생 신청 내역 (4a 목록·상세·취소: #86, 구현 기록 frontend/08, F29 / 4b 변경: #90, 구현 기록 frontend/11, F32)
- [x] BE-2 수강생 세션 보완 (A68: 2a 세션 응답·건수 완료: #91, 구현 기록 backend/66 / 2b 영상 서명 URL·스마트 메모 완료: #92, 구현 기록 backend/67 / 2c 전사 항목 완료: #93, 구현 기록 backend/68, A69)
- [x] FE-5 진행 기록·세션 상세 (F33: BE-2d 세션 목록 상태 여러 개 완료(#94, 구현 기록 backend/69) → 5a 목록·상세 완료(#95, 구현 기록 frontend/12, F34: 신청 정보 대신 [신청 보기]) → BE-2e 녹화 끝 시각 완료(#96, 구현 기록 backend/70, A71) → 5b 다시 보기 완료(#97, 구현 기록 frontend/13, F35))
- [x] FE-6 내 팀·시간 지급·차감 내역·내 정보 (F36: BE-2f 비밀번호 변경 링크 완료(#98, 구현 기록 backend/71, A72) → 6a 내 정보 완료(#99, 구현 기록 frontend/14, F37) → 6b 시간 지급·차감 내역 완료(#100, 구현 기록 frontend/15, F38) → BE-2g 내 팀 보완 완료(#101, 구현 기록 backend/72, A73) → 6c 내 팀 완료(#102, 구현 기록 frontend/16, F39))
- [x] FE-7 채팅 (F40: BE-2h 채팅 자격을 신청 이력으로 완료(#103, 구현 기록 backend/73, A74) → 7a 채팅 화면 완료(#104, 구현 기록 frontend/17) → 7b 실시간 수신·안 읽음·[채팅] 버튼 완료(#105, 구현 기록 frontend/18, F41))
- [x] FE-8 수강생 홈 (F42: BE-2i 세션 목록 정렬 완료(#106, 구현 기록 backend/74, A75) → 홈 화면 완료(#107, 구현 기록 frontend/19))
- [x] FE-9 멘토 받은 신청 (F43: BE-2j 신청 기수·수강 상태·기수 필터 완료(#108, 구현 기록 backend/75, A76) → 9a 목록 완료(#109, 구현 기록 frontend/20, F44) → 9b 상세·승인·반려 완료(#110, 구현 기록 frontend/21, F45))
- [x] FE-10 멘토 세션·기록 (F46: BE-2k 세션 목록 탭·기수 필터·세션 기수 완료(#111, 구현 기록 backend/76, A77) → 10a 목록 완료(#112, 구현 기록 frontend/22, F47) → BE-2l 기록 잔여 부족 처리 완료(#113, 구현 기록 backend/77, A78) → 10b 상세·기록·내부 메모 완료(#114, 구현 기록 frontend/23, F48) → 10c 다시 보기 완료(#115, 구현 기록 frontend/24, F50))
- [x] FE-11 멘토 일정 (F51: BE-2m 충돌 응답 주제·신청자 완료(#116, 구현 기록 backend/78, A79) → 11a 보기 완료(#117, 구현 기록 frontend/25, F52) → 11b 불가 시간 추가·수정·삭제·충돌 확인 완료(#118, 구현 기록 frontend/26, F53))
- [x] FE-12 멘토 정산·내 프로필 (F54: BE-2n 정산 응답 기수·항목 상대·주제 완료(#119, 구현 기록 backend/79, A80) → 12a 정산 완료(#120, 구현 기록 frontend/27, F55) → 12b 내 프로필 완료(#122, 구현 기록 frontend/28, F56))
- [x] FE-13 멘토 홈 (F57: 완료(#124, 구현 기록 frontend/29))
- [ ] 운영진 Figma 마무리 (F58: PR마다 그 화면만, 데스크톱 1440만)
- [x] BE-3 운영진 권한 코드 응답 (A81: `GET /me/staff-access` 완료(#125, 구현 기록 backend/82))
- [ ] FE-14 운영진 틀·홈 (F59: 14a 틀 완료(#126, 구현 기록 frontend/30) → 14b 홈은 갈 화면이 생긴 뒤로 미룸(F60))
- [x] FE-15 회원 관리·조직 설정 (F60: BE-3b 승인 후보 완료(#127, 구현 기록 backend/83, A82) → 15a 가입 승인 완료(#128, 구현 기록 frontend/31) → 15b 운영진 승인 완료(#129, 구현 기록 frontend/32, F61) → BE-3c 직원 목록 보완 완료(#130, 구현 기록 backend/84, A83) → 15c 직원·담당자 완료(#131, 구현 기록 frontend/33, F62) → BE-3d 역할별 권한 DB 판정·역할 관리 완료(#132, 구현 기록 backend/85, A84) → BE-3e 역할 보유자·직접 부여(#133, A85)는 A87로 닫음 → BE-3f 권한 엔터티 × 조회/관리 세분화 완료(#134, 구현 기록 backend/86, A86) → BE-3g 직위 = 역할 완료(#135, 구현 기록 backend/87, A87) → BE-3h 담당 역할 제거·직원 수정에서 담당 지정 완료(#136, 구현 기록 backend/88, A88·A89) → 15d 조직 설정 모듈 + 권한 완료(#137, 구현 기록 frontend/34, F63·F64·F65) → 15e 회원 관리·가입 승인 통합 완료(#138, 구현 기록 frontend/35, F66) → BE-3i 직원 목록 전체·최고 관리자 함께 수정 완료(#139, 구현 기록 backend/89, A90) → BE-3j 직원 응답에 직위 데이터 범위 완료(#140, 구현 기록 backend/90, A91) → 15f 조직 설정 > 직원 완료(#141, 구현 기록 frontend/36, F67) → BE-3k 부서·팀 직원 수 완료(#142, 구현 기록 backend/91, A92) → BE-3l 영향 조회 API 완료(#143, 구현 기록 backend/92, A93) → 15g 조직 설정 > 부서 완료(#144, 구현 기록 frontend/37, F69) → 15h 조직 설정 > 직위 완료(#145, 구현 기록 frontend/38, F70) → BE-3m 전체 회원 API 완료(#146, 구현 기록 backend/93, A94) → 15i 전체 회원 완료(#147, 구현 기록 frontend/39, F71))
- [x] FE-16 설정 (BE-3n 법정공휴일 동기화 완료(#148, 구현 기록 backend/94, A95·B16: 특일 정보 API → DB, 매일 03:00 KST 올해·내년, 조회 `{items, synced_at}`, `POST /admin/mentoring-holidays/sync`) → 공휴일 화면 완료(#149, 구현 기록 frontend/40, F72))
- [x] FE-17 학사 (F73: BE-3o 기수 요약 API 완료(#150, 구현 기록 backend/95, A96) → BE-3p 과정·기수 응답에 HRD 값 완료(#151, 구현 기록 backend/96, A97) → 17a 과정·기수 완료(#152, 구현 기록 frontend/41, F74) → BE-3q HRD 연결 정보 완료(#153, 구현 기록 backend/97, A98) → 17b HRD 과정·회차 완료(#154, 구현 기록 frontend/42, F75) → BE-3r 수강생 상세 완료(#156, 구현 기록 backend/98, A99) → 17c 수강생 완료(#157, 구현 기록 frontend/43, F76·F77) → 17d 명단 동기화 완료(#158, 구현 기록 frontend/44, F78))
- [x] FE-18 강사·멘토 (F79: BE-3s 멘토 목록 보완 완료(#159, 구현 기록 backend/99, A100) → BE-3t 멘토 단위 배정 조회 완료(#160, 구현 기록 backend/100, A101) → BE-3u 멘토 단건 조회 완료(#161, 구현 기록 backend/101, A102) → 18a 멘토 목록·상세 완료(#162, 구현 기록 frontend/45, F80) → BE-3v 계약 화면 보완 완료(#163, 구현 기록 backend/102, A103) → BE-3w 가입 전 멘토·계약 완료(#164, 구현 기록 backend/103, A104) → BE-3x 가입 연결 완료(#165, 구현 기록 backend/104, A105) → 18b 계약 완료(#166, 구현 기록 frontend/46, F81 → F82 → F83: 행정 업무 › 계약, 멘토 계약 탭) → FE-15a 보완 완료(#167, 구현 기록 frontend/47, F84) → 18c-1 기수 배정 완료(#169, 구현 기록 frontend/48, F85·F86) → BE-3y 멘토별 세션 조회 완료(#170, 구현 기록 backend/105, A106) → BE-3z 달력 참고용 휴일 조회 완료(#172, 구현 기록 backend/106, A107) → 18c-2 일정 대리 완료(#171, 구현 기록 frontend/49, F87~F89: 멘토 본인 일정도 월 달력·개인 일정 슬라이드 패널로))
- [ ] FE-19 멘토링 설정·팀
- [ ] FE-20 멘티 관리
- [ ] FE-21 신청·세션 관리
- [ ] FE-22 정산 관리
- [ ] (BE-4) FE-23 멘토링 대시보드
