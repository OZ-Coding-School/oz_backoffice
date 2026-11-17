# Frontend

OZ 통합 백오피스 프론트엔드. `apps/backend`의 REST API를 사용하는 SPA.

## 기술 스택

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| UI 라이브러리 | React 19 | 컴포넌트 기반 UI |
| 빌드/개발 서버 | Vite 8 | 번들링, HMR, 환경변수(`VITE_*`) |
| 언어 | TypeScript 7 | 정적 타입 (strict, `noUncheckedIndexedAccess`) |
| 라우터 | TanStack Router | 파일 기반 라우트(`src/routes`), 경로·검색 파라미터 타입 (decisions F5) |
| 스타일 | Tailwind CSS | 유틸리티 클래스 기반 스타일링 (디자인 토큰 PR에서 설정) |
| UI 컴포넌트 | shadcn/ui | Radix 기반 컴포넌트 (소스 복사 방식, `components/ui`, 디자인 토큰 PR에서 설정) |
| 서버 상태 | TanStack Query | API 조회/캐싱/뮤테이션, 서버 데이터의 단일 출처 |
| 클라이언트 상태 | Zustand | 인증 세션, UI 상태 등 서버와 무관한 전역 상태 |
| API 타입 | openapi-typescript + openapi-fetch | 백엔드 OpenAPI에서 타입 생성 (decisions F6, API 클라이언트 PR에서 설정) |
| 아이콘 | lucide-react | 아이콘 세트 |
| 린트 | oxlint | 정적 분석 (`--deny-warnings`, 경고도 실패) |
| 포매터 | Prettier | 기본값 + 한 줄 120자 (`.prettierrc.json`, decisions F9). `*.md`·생성 파일 제외 |

## 테스트

처음부터 아래 테스트 구성을 함께 적용한다.

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| 단위/컴포넌트 테스트 러너 | Vitest | 테스트 실행, jsdom 환경 (`src/**/*.test.ts(x)`) |
| 컴포넌트 테스트 | Testing Library | 사용자 관점의 렌더링/상호작용 검증 |
| API 모킹 | MSW | 테스트(`src/mocks/node.ts`)와 로컬 개발(`VITE_API_MOCKING=true`, `src/mocks/browser.ts`)에서 백엔드 API 응답 모킹 |
| E2E | Playwright | 빌드 결과(`vite preview`, 4173)를 실제 브라우저로 검증. API는 `page.route`로 모킹 |

## 명령어

Node 24 LTS(`.nvmrc`, CI·배포 기준)와 npm 11을 쓴다. 로컬은 Node 24 이상이면 된다(`engines`, decisions F7). **`apps/frontend`에서 실행한다.**

```bash
npm ci                    # 의존성 설치 (package-lock.json 그대로)
cp .env.example .env.local  # 최초 1회 (없으면 기본값: 백엔드 http://localhost:8000)
npm run dev               # 개발 서버 http://localhost:5173 (백엔드 CORS 기본값과 같은 포트)
npm run lint              # oxlint (경고도 실패)
npm run format            # prettier --write . (npm run format:check: 검사만)
npm run typecheck         # tsc -b
npm test                  # vitest run (npm run test:watch: 감시 모드)
npm run build             # tsc -b && vite build → dist/
npm run e2e               # playwright (로컬은 빌드 후 preview를 띄운다. 최초 1회 npx playwright install chromium)
```

- PR 전에 `lint`, `format:check`, `typecheck`, `test`, `build`, `e2e`를 모두 통과시킨다. CI(`.github/workflows/ci.yml`)도 같은 명령을 실행하고, E2E는 3개로 나눠 실행한다.
- npm 10(Node 23 이하)은 이 의존성 조합에서 설치 오류(`Cannot read properties of null (reading 'edgesOut')`)가 난다. Node 24를 쓰거나 `npx -y npm@11 install`로 설치한다.
- msw의 postinstall 스크립트는 허용하지 않았다. 브라우저 워커(`public/mockServiceWorker.js`)는 `npx msw init public`으로 만들어 커밋했다(msw 버전을 올리면 다시 만든다).

## 구조

```text
src/
├── main.tsx            # 진입점: (개발 모킹) → QueryClientProvider → RouterProvider
├── router.tsx          # createAppRouter(queryClient, history?) — 앱과 테스트가 같은 구성
├── routeTree.gen.ts    # 라우터 플러그인이 src/routes에서 생성 (커밋, 직접 고치지 않음)
├── env.ts              # VITE_* 환경 값 (apiBaseUrl = VITE_BACKEND_URL + /api/v1)
├── routes/             # 파일 기반 라우트 (__root.tsx, index.tsx …). *.test.tsx는 라우트에서 제외
├── lib/                # 앱 공통 유틸 (query-client.ts)
├── mocks/              # MSW 핸들러(handlers.ts)·브라우저 워커(browser.ts)·테스트 서버(node.ts)
└── test/               # Vitest 설정(setup.ts)·렌더 도우미(render.tsx: renderRoute)
e2e/                    # Playwright 시나리오
```

- import 경로는 `@/` 별칭(= `src/`)을 쓴다.
- 테스트는 `renderRoute(path)`로 앱과 같은 라우터·Query 구성에서 렌더링한다. 모킹하지 않은 API 요청은 실패한다(`onUnhandledRequest: 'error'`).
- 새 라우트 파일을 추가하면 `npm run dev`나 `npm run build`가 `routeTree.gen.ts`를 다시 만든다. 바뀐 생성 파일도 함께 커밋한다(타입 검사가 이 파일을 쓴다).

## 상태 관리 원칙

- 서버에서 온 데이터는 TanStack Query로만 관리한다. Zustand에 복사해 두지 않는다.
- Zustand는 클라이언트 전용 상태(로그인 세션 정보, 사이드바, 필터 UI 등)에만 사용한다.
- 목록의 필터·페이지는 라우터 검색 파라미터로 두어 새로고침·공유에도 유지한다.

---

# 작업 하네스

프론트엔드 작업을 할 때 따르는 절차와 기준이다. 린트·포맷·타입은 oxlint·Prettier·tsc가 강제하고, 여기 적힌 나머지는 이 문서와 리뷰가 지킨다.

## 1. 작업 시작 전

1. **계획 확인:** `docs/implement_plans/mentoring_phase1_frontend.md`에서 이번 PR(FE-*·BE-*)의 범위·API·선행 PR을 읽는다. 공통 규약(§2)을 따른다.
2. **결정 확인:** `docs/decisions.md`의 F1~F17과 화면에 걸린 업무 규칙(멘토링이면 M·A 항목, 예: 취소 A44, 기록 A53, 채팅 A57·A58)을 읽는다. 결정과 다르게 구현해야 할 것 같으면 구현하지 말고 먼저 묻는다.
3. **디자인 확인:** Figma 파일(fileKey `qOkjzhLBT7aS0STGDxokfN`)에서 해당 화면(`Screen / <이름>`)과 **캡션**(쓰는 API·규칙 메모)을 읽는다. Figma MCP를 쓸 때는 figma-use·figma-design-to-code 스킬을 먼저 불러온다. 디자인에 없는 상태(빈 목록·로딩·오류·권한 없음)는 같은 페이지의 비슷한 화면과 디자인 시스템 컴포넌트로 맞추고, 새 화면 구성이 필요하면 묻는다.
4. **범위 밖 요소 제외 (F15):** 디자인에 이번 범위가 아닌 요소(헬프센터·내 문서함·출결·행정·디스코드·알림 등, 계획 §0 제외표)가 있으면 **메뉴·탭·카드·링크까지 넣지 않고** 범위 안 요소만 구현한다. 자리만 남기거나 "준비 중" 화면을 만들지 않는다.
5. **API 확인:** 백엔드 OpenAPI(`http://localhost:8000/docs`)와 생성 타입에서 요청·응답·오류 코드를 확인한다. 화면에 필요한 API가 없거나 응답 필드가 모자라면 프론트에서 우회하지 말고 계획의 백엔드 보완 PR로 돌리거나 묻는다.
6. **브랜치 확인:** `develop`에서 만든 작업 브랜치인지 확인한다. (`main`·`develop` 직접 커밋 금지, README 참고)
7. **결정이 필요한 사항은 반드시 사용자에게 묻고 진행한다. 임의로 정하지 않는다.** 화면 구성·흐름 변경, 디자인과 다른 구현, 경로(URL) 변경, 새 의존성, 상태 관리 방식, 문구 정책, PR 분할이 모두 해당한다. 권장안이 있으면 선택지에 "(Recommended)"로 제시하되 답을 받은 뒤에 반영하고, 확정된 결정은 `docs/decisions.md` §5에 기록한다. 이미 정해진 내용과 기존 코드 패턴을 그대로 따르는 구현 세부만 묻지 않고 진행한다.

## 2. 구현 순서 (데이터에서 화면으로)

화면 하나(기능 하나)를 아래 순서로 만든다. 단계마다 해당 테스트를 함께 쓴다.

| 순서 | 위치 | 만드는 것 | 테스트 |
| --- | --- | --- | --- |
| 1 | `src/api` | 백엔드가 바뀌었으면 `npm run api:gen`으로 타입을 다시 만든다 | typecheck |
| 2 | `features/<기능>/api.ts` | Query 키 팩토리, 조회 훅(`useQuery`/`useInfiniteQuery`), 뮤테이션 훅과 무효화 | — |
| 3 | `mocks/handlers` | 생성 타입을 쓰는 MSW 핸들러(성공·대표 오류 코드) | — |
| 4 | `features/<기능>/schemas.ts`, `messages.ts` | 폼 Zod 스키마, 오류 코드 → 문구 표 | 단위 테스트(경계값) |
| 5 | `features/<기능>/components` | 화면 조각 (디자인 시스템 컴포넌트 조합) | 컴포넌트 테스트(상호작용, 성공·오류·빈 상태) |
| 6 | `routes/` | 라우트 파일: 검색 파라미터 검증, `loader`에서 `ensureQueryData`로 미리 불러오기, 화면 조립만 | `renderRoute` 테스트 |
| 7 | `e2e/` | 핵심 흐름 1~2개 | Playwright |
| 8 | 문서 | 새 결정은 `docs/decisions.md`, 완료 시 구현 기록·계획 체크리스트 | — |

## 3. 코드 작성 유의사항

### 공통
- **타입:** strict·`noUncheckedIndexedAccess`를 통과해야 한다. `any`·`as` 단언·`@ts-expect-error`는 외부 경계에서만 쓰고 이유를 주석으로 남긴다. API 타입은 생성 타입에서 가져오고 손으로 다시 정의하지 않는다(`schema.gen.ts`는 직접 고치지 않음).
- **서버 상태:** 서버 데이터는 TanStack Query로만 다룬다. 응답을 Zustand·`useState`에 복사하지 않는다. 쓰기 뒤에는 관련 Query 키를 무효화하거나 응답으로 캐시를 고친다(낙관적 업데이트는 채팅처럼 필요할 때만).
- **클라이언트 상태:** Zustand는 세션·현재 기수·UI 상태에만 쓴다. 목록 필터·페이지·탭은 라우터 검색 파라미터에 둔다.
- **폼:** React Hook Form + Zod(F16). 서버 검증(422)과 도메인 오류 코드는 해당 필드나 폼 상단 Alert로 보여 준다. 제출 중에는 버튼을 막아 중복 제출을 막는다.
- **시각:** 날짜·시간은 공용 도우미(date-fns + @date-fns/tz, Asia/Seoul)로만 표시·변환한다. `new Date().toLocaleString()`처럼 브라우저 시간대에 기대는 코드를 쓰지 않는다. 시간·분은 정수로 다룬다.
- **스타일:** 색·글자·간격·모서리는 디자인 토큰(Tailwind 테마·CSS 변수)만 쓴다. hex 값·임의 px을 직접 쓰지 않는다. 라이트·다크 둘 다 확인한다. 상태 색 규칙(F14: 배지·띠·배경만, 텍스트에는 상태 색 없음)을 지킨다.
- **컴포넌트:** `components/ui`(shadcn)를 먼저 쓰고, 두 기능 이상에서 쓰는 조각만 `components/`로 올린다. 한 기능에서만 쓰는 조각은 `features/<기능>/components`에 둔다.
- **문구:** 사용자 문구는 한국어, Figma 문구를 그대로 쓴다. 시간 보류는 '차감 예정'(F14). 오류 문구는 `messages.ts` 표에서 가져온다.
- **마크다운:** 공용 `<Markdown>` 컴포넌트만 쓴다(F4·F16). `dangerouslySetInnerHTML`을 쓰지 않는다.
- **접근성:** 버튼·링크는 실제 `button`·`a`(라우터 `Link`)로 만들고, 아이콘만 있는 버튼에는 `aria-label`을 단다. 폼 입력은 label과 연결하고, 모달은 포커스를 가둔다(shadcn Dialog). 키보드로 주요 흐름을 끝까지 할 수 있어야 한다.
- **보안·개인정보:** access 토큰을 localStorage·sessionStorage·쿠키에 저장하지 않는다(메모리만, A7). 개인정보(이메일·전화번호)와 토큰을 `console`·오류 리포트에 남기지 않는다. 외부 링크는 `rel="noopener noreferrer"`.
- **환경 값:** `VITE_*`는 `src/env.ts`에만 추가하고 `.env.example`에도 키를 추가한다. 시크릿을 프론트 환경 값에 넣지 않는다(번들에 그대로 들어간다).
- **의존성 추가:** 정해진 라이브러리(F1·F16)는 쓰는 PR에서 정확한 버전으로 설치한다. 그 밖의 새 라이브러리는 이유를 설명하고 확인받는다.

## 4. 성능 기준

| 항목 | 기준 |
| --- | --- |
| 코드 분할 | 라우트 단위 분할(라우터 플러그인 자동)을 유지한다. 무거운 라이브러리(Shiki 언어, 차트, 영상 플레이어)는 쓰는 화면에서 지연 로드한다 |
| 요청 폭포 | 화면에 필요한 조회는 라우트 `loader`에서 병렬로 미리 불러온다. 자식 컴포넌트가 차례로 조회하게 만들지 않는다 |
| 다시 조회 | Query 기본값(staleTime 30초)을 따르고, 자주 바뀌는 데이터(채팅)는 SSE 이벤트로 캐시를 고친다. 폴링이 필요하면 이유를 적는다 |
| 렌더링 | 긴 목록(채팅 메시지, 원장)은 커서로 나눠 불러오고, 수백 행을 넘으면 가상 스크롤을 검토한다. 큰 계산은 `useMemo`, 불필요한 리렌더는 React DevTools로 확인한다 |
| 번들 | `npm run build` 출력에서 초기 청크 크기를 확인하고, 크게 늘었으면 PR 본문에 원인을 적는다 |
| 이미지 | 업로드 전 브라우저에서 줄이고(멘토 사진 A28), 목록 이미지는 크기를 지정해 레이아웃이 흔들리지 않게 한다 |

## 5. 테스트 기준

- 버그를 고치면 그 버그를 재현하는 테스트를 먼저 추가한다.
- 컴포넌트 테스트는 사용자 관점(Testing Library의 역할·라벨 쿼리)으로 쓰고, 구현 세부(상태 값, 클래스 이름)를 검사하지 않는다.
- 화면마다 성공, 대표 오류 코드, 빈 상태, 로딩을 검사한다. 권한에 따라 숨기는 메뉴·버튼은 보이는 경우와 숨는 경우를 둘 다 검사한다.
- API는 MSW로만 모킹한다(모킹하지 않은 요청은 실패). 시각은 `vi.setSystemTime`으로 고정한다.
- 폼 스키마·날짜 변환·SSE 파서·인증 미들웨어 같은 순수 로직은 단위 테스트로 경계값을 검사한다.
- E2E는 화면 PR마다 핵심 흐름만 둔다. 같은 흐름을 컴포넌트 테스트와 중복으로 길게 쓰지 않는다.

## 6. 커밋 단위

- **커밋 하나 = 논리적 변경 하나.** 커밋마다 `lint`·`format:check`·`typecheck`·`test`가 통과하는 상태여야 한다.
- 코드와 그 코드의 테스트·MSW 핸들러는 같은 커밋에 넣는다. 생성 파일(`schema.gen.ts`, `routeTree.gen.ts`)은 그 파일을 바꾼 변경과 같은 커밋에 넣는다.
- 기능 변경과 리팩터링, 포맷 변경, 의존성 추가를 섞지 않는다. 의존성은 쓰는 코드와 함께 넣되 별도 커밋으로 둘 수 있다.
- 결정이 생긴 변경이면 `docs/decisions.md` 수정을 그 커밋에 포함한다.
- 크기 기준: 생성 파일·잠금 파일을 빼고 300줄 안팎.
- 메시지: `<타입>: <한글 설명>` (README, `.github/commit_template.txt`). 본문에 무엇을, 왜.

예) "멘토 받은 신청" 브랜치의 커밋 흐름
```text
feat: 멘토 받은 신청 조회·승인·반려 훅과 MSW 핸들러 추가
feat: 멘토 받은 신청 목록 화면 추가
feat: 멘토 신청 상세 페이지와 일시 선택 승인 추가
feat: 신청 반려 확인 창 추가
test: 멘토 신청 승인 E2E 추가
docs: 멘토 받은 신청 구현 기록 추가
```

## 7. PR 단위

- **PR 하나 = 사용자가 확인할 수 있는 화면 묶음 하나.** 계획 문서의 FE-* 단위를 따르고, 크면 화면 단위로 나눈다(예: FE-3a/3b). 나누는 방식은 시작할 때 확인받는다.
- 크기 기준: 생성 파일·잠금 파일을 빼고 변경 600줄 안팎.
- 백엔드 보완(BE-*)은 화면 PR과 섞지 않고 백엔드 PR로 먼저 병합한 뒤 `api:gen`으로 타입을 받는다.
- 리팩터링·의존성 업데이트·설정 변경은 기능 PR과 분리한다.
- PR 본문에 구현한 Figma 화면 이름과 **제외한 범위 밖 요소**(F15)를 적고, 화면 스크린샷(라이트·다크, 모바일이 있으면 390)을 붙인다.
- 구현 기록(`docs/implement_descriptions/frontend/NN_*.md`)과 계획 문서 체크리스트 갱신은 같은 PR에 넣는다.
- PR 전에 최신 `develop`으로 rebase하고 전체 검사를 다시 돌린다.

### 멘토링 1단계 PR 순서
PR 순서와 PR별 화면·API는 **`docs/implement_plans/mentoring_phase1_frontend.md`** 를 따른다. (FE-0 초기 세팅 → FE-1 인증 → BE-1 → FE-2~FE-8 수강생 → FE-9~FE-13 멘토 → 운영진 Figma 마무리 → BE-3 → FE-14~FE-23 운영진)
PR을 시작할 때 해당 절과 선행 준비물을 먼저 확인하고, 끝나면 그 문서의 진행 체크리스트를 갱신한다.

## 8. 완료 기준 (Definition of Done)

- [ ] `npm run lint`, `npm run format:check`, `npm run typecheck`
- [ ] `npm test`, `npm run build`, `npm run e2e` — 실제로 실행한다. 못 했으면 못 했다고 보고한다
- [ ] `npm run dev`로 띄워 화면을 직접 확인했다(라이트·다크, 모바일 화면이 있으면 390 폭). 가능하면 로컬 백엔드와 연결해 실제 응답으로도 확인한다
- [ ] Figma 화면과 비교해 레이아웃·문구·상태 표시가 맞고, 범위 밖 요소를 넣지 않았다
- [ ] 백엔드 API가 바뀌었으면 생성 타입·MSW 핸들러가 맞는다
- [ ] 새 결정은 `docs/decisions.md`, 완료 시 구현 기록과 계획 체크리스트 갱신
- [ ] 결과 보고에 실행한 검사와 실행하지 못한 검사를 구분해서 적는다

## 9. 하지 말 것

- 결정(`docs/decisions.md`)이나 Figma 디자인과 다른 구현을 확인 없이 진행하기
- 결정이 필요한 사항을 사용자에게 묻지 않고 임의로 정해 구현하기 (§1-7)
- 범위 밖 화면 구성(F15)을 자리만이라도 구현하기
- 없는 API를 프론트에서 우회해 만들기(여러 API를 억지로 조합해 규칙을 흉내 내기, 서버가 할 판정을 프론트에만 두기)
- 실패하는 테스트를 건너뛰기(`skip`)·삭제·기대값 완화로 통과시키기, 린트 규칙을 끄거나 `--deny-warnings`를 빼서 통과시키기
- 생성 파일(`schema.gen.ts`, `routeTree.gen.ts`)을 손으로 고치기
- access 토큰을 브라우저 저장소에 저장하기, 개인정보·토큰을 콘솔에 남기기
- `main`·`develop`에 직접 커밋·push, 강제 push(본인 작업 브랜치의 `--force-with-lease` 제외)
