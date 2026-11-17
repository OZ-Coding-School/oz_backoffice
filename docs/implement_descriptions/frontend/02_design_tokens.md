# 02. 디자인 토큰 (Tailwind·shadcn 테마, 글꼴, 다크 모드)

- 상태: 완료 (2026-11-17 병합)
- 관련 PR: #72
- 관련 결정: `docs/decisions.md` F8·F18, 계획 `docs/implement_plans/mentoring_phase1_frontend.md` FE-0a
- 이전 기록: [01. 프론트엔드 프로젝트 도구·테스트 구성](01_frontend_project_setup.md)

## 배경
초기 세팅 PR 3개(F8) 중 두 번째다. Figma `Design System` 페이지의 변수(라이트·다크)·텍스트 스타일·그림자를 코드 테마로 옮기고, 화면 PR에서 공통으로 쓸 글꼴·다크 모드·기본 컴포넌트를 준비한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `src/styles/index.css` | Tailwind v4 진입점. 글꼴 import, `.dark` 변형, `:root`(라이트)·`.dark`(다크) 색 변수, `@theme inline`(색·글자·모서리·그림자), 기본 스타일(본문 색·글꼴·포커스 링) |
| `src/styles/tokens.md` | Figma 변수·스타일 ↔ CSS 변수·Tailwind 클래스 대응표 |
| `src/lib/theme.ts` | 테마 선택(시스템·라이트·다크) 읽기·저장·적용, 시스템 변경 따라가기, `useTheme` 훅 |
| `index.html` | 앱 번들보다 먼저 테마를 적용하는 인라인 스크립트(첫 화면 깜빡임 방지) |
| `src/lib/utils.ts` | `cn()` (clsx + tailwind-merge) |
| `src/components/ui/button.tsx`, `badge.tsx`, `input.tsx` | Figma `Components`의 Button(6변형 × md·sm, 비활성)·Badge(8변형)·Input(기본·포커스·오류·비활성) |
| `src/routes/dev/design-system.tsx` | 토큰·컴포넌트 확인 화면. 개발 서버에서만 열리고 운영 빌드에서는 없는 경로 |
| `components.json` | shadcn CLI 설정(별칭·CSS 경로). 다음 컴포넌트는 CLI로 추가한 뒤 Figma에 맞춰 고친다 |
| `vite.config.ts`, `src/main.tsx` | Tailwind 플러그인, CSS import, 시작 시 테마 적용 |
| `apps/frontend/CLAUDE.md` | 스택 표·구조·토큰 사용 규칙 갱신 |

**설치한 의존성 (정확한 버전):** tailwindcss·@tailwindcss/vite 4.3.5, class-variance-authority 0.7.1, clsx 2.1.1, tailwind-merge 3.7.0, radix-ui 1.8.1(Slot), lucide-react 1.74.0, @fontsource-variable/noto-sans-kr 5.3.1, @fontsource/fira-code 5.3.0

## 주요 결정 (사용자 결정, F18)
- Tailwind **v4 + `@tailwindcss/vite`**, 설정은 CSS `@theme`.
- 색 토큰은 **shadcn 표준 이름 + 추가 토큰**(상태 subtle·text, primary-hover·primary-text, brand-panel). Figma 대응표를 둔다.
- 글꼴은 **앱에 포함**. 한글은 처음에 굵기별 글꼴(400·500·700)로 넣었다가, 글꼴 CSS만 276kB라 **가변 글꼴로 바꿨다**(아래 문제와 해결).
- 다크 모드는 **시스템·라이트·다크 3가지**, 기본은 시스템, `localStorage`에 기억, `index.html`에서 먼저 적용.
- 컴포넌트는 **토큰 + Button·Badge·Input**만. 나머지는 쓰는 화면 PR에서 추가한다.
- **Figma에 없는 hover·focus**: Primary는 `primary-hover`, Secondary·Outline·Ghost는 `accent` 배경 + `accent-foreground`, Destructive는 90% 불투명, Link는 밑줄. 키보드 포커스는 ring 2px.
- 확인 화면은 **개발 모드 전용 경로**(`/dev/design-system`). 상단 막대의 테마 버튼 모양은 FE-2에서 정한다.

## 구현 세부
- Tailwind 기본 색 팔레트와 글자 크기는 `@theme`에서 지웠다(`--color-*: initial`, `--text-*: initial`). 하네스의 "토큰만 쓴다" 규칙을 빌드에서 강제하기 위해서다. `white`·`black`만 남겼다.
- 텍스트 스타일은 Tailwind v4의 `--text-<이름>--line-height/--letter-spacing/--font-weight`로 한 클래스에 묶었다(`text-h1` 하나로 24/32 Bold -0.3px).
- 간격(4px 단위)과 모서리(4·6·8·12px)는 Tailwind 기본값이 Figma와 같아 그대로 쓴다. 그림자는 Figma 값으로 바꿨다.
- 색 변수는 hex로 옮겼다(Figma 값과 1:1 대조가 쉽도록). 투명도 변형(`bg-destructive/90`)은 Tailwind가 `color-mix`로 만든다.
- Button은 `type`을 지정하지 않으면 `button`으로 둔다(폼 안 의도치 않은 제출 방지). `asChild`로 라우터 `Link`에 스타일을 입힐 수 있다.
- Input 오류 상태는 `aria-invalid`로 표시한다(React Hook Form과 연결하기 쉽도록). 라벨·도움말을 묶는 폼 필드 조각은 폼을 쓰는 PR(FE-1)에서 만든다.
- 테마 상태는 Zustand를 설치하지 않고 `useSyncExternalStore`로 만들었다(값 하나라 의존성이 필요 없음).

## 발견한 문제와 해결
- **글꼴 CSS가 컸다:** `@fontsource/noto-sans-kr`의 굵기별 CSS는 유니코드 범위 124개 × 2형식이라 굵기마다 92kB, 세 굵기 276kB였다(빌드 CSS 281kB, gzip 93kB, 첫 화면을 막는 CSS). 사용자 확인 후 가변 글꼴 `@fontsource-variable/noto-sans-kr` 하나로 바꿔 빌드 CSS를 **104kB(gzip 36kB)**로 줄였다. 글꼴 파일도 굵기별로 따로 받지 않는다.
- **E2E 타입 검사:** `e2e`는 DOM 타입이 없는 tsconfig라 `window`·`document`를 직접 쓰면 타입 오류가 난다. 브라우저 코드는 문자열(`addInitScript({ content })`, `page.evaluate("…")`)로 넘겼다.

## 검증
- 로컬(Node 26.13, npm 11.20)
  - `npm run lint`(경고 0), `npm run format:check`, `npm run typecheck`: 통과
  - `npm test`: 21 passed (테마 6, Button 4, Badge 4, Input 3, 확인 화면 2, 기존 홈 2)
  - `npm run build`: 통과 (CSS 104.68kB / gzip 36.37kB)
  - `npm run e2e`: 5 passed (기존 홈 1 + 시스템 다크 첫 화면 적용, 고른 테마 기억, 글꼴 적용·한글 글꼴 로드, 운영 빌드에 확인 화면 없음)
- `npm run dev`로 `/dev/design-system`을 라이트·다크로 띄워 Figma 토큰(색·글자·그림자·모서리)과 Button·Badge·Input을 눈으로 비교했다.
- `npx shadcn@4.23.0 add separator --dry-run`으로 CLI가 `components.json`을 읽는지 확인했다(실제로 추가하지는 않음).

- GitHub Actions (PR #72): 프론트엔드 검사 잡과 E2E 3개 통과
- 사용자가 병합을 확인했다(2026-11-17)

## 남은 작업
- FE-0b API 클라이언트(OpenAPI 타입 생성, openapi-fetch, 인증 미들웨어)
- 상단 막대의 테마 전환 버튼 모양(FE-2), 폼 필드 조각(라벨·도움말·오류, FE-1)
