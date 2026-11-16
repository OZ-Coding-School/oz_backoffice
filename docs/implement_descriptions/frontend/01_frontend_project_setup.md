# 01. 프론트엔드 프로젝트 도구·테스트 구성

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` F1·F2·F5~F8

## 배경
멘토링 1단계 백엔드(P1~P15)와 운영진 화면용 API 보완(A59)이 끝났다. Figma 디자인을 화면으로 옮기기 전에 프론트엔드 앱을 만든다. 초기 세팅은 PR 3개로 나누기로 했다(F8). 이 기록은 그 첫 번째인 도구·테스트 구성이다. 디자인 토큰과 API 클라이언트는 다음 PR에서 한다. CI에는 프론트엔드 단계(lint·typecheck·test·build·E2E 3분할)가 이미 준비돼 있었고, `package.json`이 생기면 실행된다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `apps/frontend/package.json`, `package-lock.json` | 스크립트 `dev`·`build`·`preview`·`lint`·`typecheck`·`test`·`e2e`. 의존성 버전은 정확한 값으로 고정했다. |
| `.nvmrc` | Node 24 |
| `vite.config.ts` | TanStack Router 플러그인(파일 기반, 코드 분할 자동, `*.test.tsx` 제외), React 플러그인, `@` 별칭, dev 5173·preview 4173 포트, Vitest(jsdom) 설정 |
| `tsconfig*.json` | strict, `noUncheckedIndexedAccess`. 앱과 설정 파일(vite·playwright·e2e)을 나눴다. |
| `.oxlintrc.json` | correctness는 오류, suspicious는 경고로 둔다. 스크립트에 `--deny-warnings`를 붙여 경고도 실패로 처리한다. 라우트 파일에서는 `only-export-components`를 끈다. |
| `playwright.config.ts` | chromium. CI에서는 앞 단계 빌드를 쓰고 preview만 띄우며, 로컬에서는 빌드부터 한다. |
| `src/main.tsx`, `router.tsx`, `routeTree.gen.ts` | QueryClientProvider와 RouterProvider. 라우터 컨텍스트로 queryClient를 넘긴다. |
| `src/env.ts`, `vite-env.d.ts`, `.env.example` | `VITE_BACKEND_URL`(기본 `http://localhost:8000`), `VITE_API_MOCKING` |
| `src/lib/query-client.ts` | Query 기본값: staleTime 30초, 재시도 1회, 창 포커스 시 다시 조회하지 않음 |
| `src/routes/__root.tsx`, `index.tsx` | 루트 레이아웃, 없는 경로 안내, 홈 자리표시 |
| `src/mocks/*`, `public/mockServiceWorker.js` | MSW 핸들러, 브라우저 워커(로컬 개발 모킹), 테스트 서버 |
| `src/test/setup.ts`, `render.tsx` | jest-dom, MSW 서버(모킹하지 않은 요청은 실패), `renderRoute(path)` |
| `src/routes/index.test.tsx`, `e2e/home.spec.ts` | 홈 화면과 없는 경로 단위 테스트, 홈 E2E |
| `apps/frontend/CLAUDE.md` | 스택·명령어·구조·규칙 |

**주요 버전:** React 19.3, Vite 8.3, TypeScript 7.0, TanStack Router 1.170·Query 5.107, Vitest 5.1, MSW 2.15, Playwright 1.65, oxlint 1.93

## 주요 결정
- **사용자 결정**
  - 라우터는 TanStack Router(F5).
  - API 타입은 OpenAPI에서 자동 생성(F6, 세 번째 PR).
  - Node 24 LTS와 npm(F7).
  - 초기 세팅은 PR 3개로 나눈다(F8).
- **Tailwind·shadcn·lucide·Zustand·openapi는 쓰는 PR에서 설치한다.** 이 PR에는 쓰지 않는 의존성을 넣지 않았다.
- **`routeTree.gen.ts`는 커밋한다.** CI의 typecheck가 build보다 먼저 실행되기 때문이다.
- **MSW 브라우저 워커는 개발 모드에서 `VITE_API_MOCKING=true`일 때만 켠다.** 운영 빌드에는 워커를 올리지 않는다.

## 발견한 문제와 해결
- **npm 10(로컬 Node 23)에서 설치 오류:** jsdom·vitest 5를 설치할 때 `Cannot read properties of null (reading 'edgesOut')`가 났다(npm arborist 문제). Node 24에 포함된 npm 11(`npx -y npm@11 install`)로는 정상 설치됐고, 잠금 파일도 npm 11로 만들었다. CI는 Node 24라 npm 11을 쓴다.
- **msw postinstall 스크립트:** npm 11이 실행을 막았다. 워커 파일은 `npx msw init public`으로 직접 만들어 커밋했다.
- **jsdom의 `scrollTo` 미구현 경고:** 라우터의 스크롤 복원이 부른다. 테스트 설정에서 빈 함수로 둔다.

## 검증
- 로컬(Node 23.11, npm 11로 설치)
  - `npm run lint`: 경고 0
  - `npm run typecheck`: 통과
  - `npm test`: 2 passed
  - `npm run build`: 통과
  - `npm run e2e`: 1 passed (chromium)

## 남은 작업
- 두 번째 PR: 디자인 토큰(Figma 라이트·다크 → Tailwind·shadcn 테마), 폰트, 다크 모드 전환
- 세 번째 PR: API 클라이언트(OpenAPI 타입 생성, openapi-fetch, 토큰 갱신)
- 배포(Vercel, R4) 설정은 화면이 생긴 뒤에 한다.
