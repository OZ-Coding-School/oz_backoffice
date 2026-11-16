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

## 테스트

처음부터 아래 테스트 구성을 함께 적용한다.

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| 단위/컴포넌트 테스트 러너 | Vitest | 테스트 실행, jsdom 환경 (`src/**/*.test.ts(x)`) |
| 컴포넌트 테스트 | Testing Library | 사용자 관점의 렌더링/상호작용 검증 |
| API 모킹 | MSW | 테스트(`src/mocks/node.ts`)와 로컬 개발(`VITE_API_MOCKING=true`, `src/mocks/browser.ts`)에서 백엔드 API 응답 모킹 |
| E2E | Playwright | 빌드 결과(`vite preview`, 4173)를 실제 브라우저로 검증. API는 `page.route`로 모킹 |

## 명령어

Node 24 LTS(`.nvmrc`)와 그에 포함된 npm 11을 쓴다(decisions F7). **`apps/frontend`에서 실행한다.**

```bash
npm ci                    # 의존성 설치 (package-lock.json 그대로)
cp .env.example .env.local  # 최초 1회 (없으면 기본값: 백엔드 http://localhost:8000)
npm run dev               # 개발 서버 http://localhost:5173 (백엔드 CORS 기본값과 같은 포트)
npm run lint              # oxlint (경고도 실패)
npm run typecheck         # tsc -b
npm test                  # vitest run (npm run test:watch: 감시 모드)
npm run build             # tsc -b && vite build → dist/
npm run e2e               # playwright (로컬은 빌드 후 preview를 띄운다. 최초 1회 npx playwright install chromium)
```

- PR 전에 `lint`, `typecheck`, `test`, `build`, `e2e`를 모두 통과시킨다. CI(`.github/workflows/ci.yml`)도 같은 명령을 실행하고, E2E는 3개로 나눠 실행한다.
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
