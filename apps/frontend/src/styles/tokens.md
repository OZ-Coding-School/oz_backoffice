# 디자인 토큰 대응표

Figma 파일 `Design System` 페이지의 변수·스타일과 코드(`src/styles/index.css`)의 대응이다 (decisions F18).
색은 shadcn 표준 이름을 쓰고, 표준에 없는 것만 같은 규칙으로 추가했다. Tailwind 클래스는 `bg-<이름>`, `text-<이름>`, `border-<이름>`처럼 쓴다.
Figma 값을 바꾸면 `index.css`의 `:root`(라이트)·`.dark`(다크)와 이 표를 함께 고친다.

## 색 (Figma `Color` 컬렉션, Light / Dark)

| Figma 변수 | CSS 변수 | Tailwind | Light | Dark |
| --- | --- | --- | --- | --- |
| base/background | `--background` | `bg-background` | #ffffff | #1f1f23 |
| base/foreground | `--foreground` | `text-foreground` | #09090b | #fafafa |
| surface/card | `--card` | `bg-card` | #ffffff | #27272a |
| surface/card-foreground | `--card-foreground` | `text-card-foreground` | #09090b | #fafafa |
| surface/popover | `--popover` | `bg-popover` | #ffffff | #27272a |
| surface/popover-foreground | `--popover-foreground` | `text-popover-foreground` | #09090b | #fafafa |
| surface/muted | `--muted` | `bg-muted` | #f4f4f5 | #323238 |
| surface/muted-foreground | `--muted-foreground` | `text-muted-foreground` | #71717a | #a1a1aa |
| brand/primary | `--primary` | `bg-primary` | #7c3aed | #7c3aed |
| brand/primary-hover | `--primary-hover` (추가) | `bg-primary-hover` | #6d28d9 | #6d28d9 |
| brand/primary-foreground | `--primary-foreground` | `text-primary-foreground` | #ffffff | #ffffff |
| brand/primary-text | `--primary-text` (추가) | `text-primary-text` | #6d28d9 | #c4b5fd |
| brand/secondary | `--secondary` | `bg-secondary` | #f4f4f5 | #323238 |
| brand/secondary-foreground | `--secondary-foreground` | `text-secondary-foreground` | #18181b | #fafafa |
| brand/accent | `--accent` | `bg-accent` | #f5f3ff | #2e1065 |
| brand/accent-foreground | `--accent-foreground` | `text-accent-foreground` | #6d28d9 | #ddd6fe |
| brand/brand-panel | `--brand-panel` (추가) | `bg-brand-panel` | #7c3aed | #4c1d95 |
| line/border | `--border` | `border-border` | #e4e4e7 | #3f3f46 |
| line/input | `--input` | `border-input` | #d4d4d8 | #3f3f46 |
| line/ring | `--ring` | `ring-ring` | #8b5cf6 | #a78bfa |
| status/destructive | `--destructive` | `bg-destructive` | #dc2626 | #ef4444 |
| status/destructive-foreground | `--destructive-foreground` | `text-destructive-foreground` | #ffffff | #ffffff |
| status/destructive-subtle | `--destructive-subtle` (추가) | `bg-destructive-subtle` | #fef2f2 | #450a0a |
| status/destructive-text | `--destructive-text` (추가) | `text-destructive-text` | #dc2626 | #f87171 |
| status/success | `--success` (추가) | `bg-success` | #16a34a | #22c55e |
| status/success-subtle | `--success-subtle` (추가) | `bg-success-subtle` | #f0fdf4 | #052e16 |
| status/success-text | `--success-text` (추가) | `text-success-text` | #16a34a | #4ade80 |
| status/warning | `--warning` (추가) | `bg-warning` | #f59e0b | #fbbf24 |
| status/warning-subtle | `--warning-subtle` (추가) | `bg-warning-subtle` | #fffbeb | #451a03 |
| status/warning-text | `--warning-text` (추가) | `text-warning-text` | #d97706 | #fbbf24 |
| status/info | `--info` (추가) | `bg-info` | #2563eb | #3b82f6 |
| status/info-subtle | `--info-subtle` (추가) | `bg-info-subtle` | #eff6ff | #172554 |
| status/info-text | `--info-text` (추가) | `text-info-text` | #2563eb | #60a5fa |
| sidebar/sidebar | `--sidebar` | `bg-sidebar` | #fafafa | #27272a |
| sidebar/sidebar-foreground | `--sidebar-foreground` | `text-sidebar-foreground` | #3f3f46 | #d4d4d8 |
| sidebar/sidebar-accent | `--sidebar-accent` | `bg-sidebar-accent` | #ede9fe | #2e1065 |
| sidebar/sidebar-accent-foreground | `--sidebar-accent-foreground` | `text-sidebar-accent-foreground` | #6d28d9 | #ddd6fe |
| sidebar/sidebar-border | `--sidebar-border` | `border-sidebar-border` | #e4e4e7 | #3f3f46 |

Tailwind 기본 색 팔레트(`bg-violet-600` 등)는 지웠다. `white`·`black`만 남긴다. `Primitives` 컬렉션(violet·zinc …)은 위 의미 색의 원본이라 코드에 따로 두지 않는다.

## 글자 (Figma 텍스트 스타일)

한 클래스가 크기·줄 높이·자간·굵기를 함께 정한다. Tailwind 기본 글자 크기(`text-sm` 등)는 지웠다.

| Figma 스타일 | 클래스 | 크기/줄 높이 | 굵기 | 자간 |
| --- | --- | --- | --- | --- |
| Display | `text-display` | 30/38 | Bold 700 | -0.5px |
| Heading/H1 | `text-h1` | 24/32 | Bold 700 | -0.3px |
| Heading/H2 | `text-h2` | 20/28 | Bold 700 | -0.2px |
| Heading/H3 | `text-h3` | 16/24 | Bold 700 | 0 |
| Body/Large | `text-body-lg` | 16/24 | Regular 400 | 0 |
| Body/Default | `text-body` (본문 기본) | 14/20 | Regular 400 | 0 |
| Body/Strong | `text-body-strong` | 14/20 | Medium 500 | 0 |
| Body/Small | `text-body-sm` | 13/18 | Regular 400 | 0 |
| Label/Default | `text-label` | 13/18 | Medium 500 | 0 |
| Caption | `text-caption` | 12/16 | Regular 400 | 0 |
| Caption/Strong | `text-caption-strong` | 12/16 | Medium 500 | 0 |

- 글꼴: `font-sans` = Noto Sans KR(가변 글꼴), `font-mono` = Fira Code(시각·코드). 둘 다 앱에 포함한다.

## 간격·모서리·그림자

| Figma | 코드 |
| --- | --- |
| `Spacing` spacing/N (4px 단위: 0.5=2, 1=4 … 16=64) | Tailwind 기본 간격 그대로 (`p-4` = 16px) |
| `Radius` sm 4 / md 6 / lg 8 / xl 12 / full | `rounded-sm` / `rounded-md` / `rounded-lg` / `rounded-xl` / `rounded-full` |
| Shadow/sm·md·lg | `shadow-sm` / `shadow-md` / `shadow-lg` |

## 다크 모드

- 루트(`<html>`)의 `.dark` 클래스로 켠다. `dark:` 변형도 이 클래스를 따른다.
- 고른 값(시스템·라이트·다크)은 `localStorage`의 `oz-theme`에 둔다. `index.html`의 스크립트가 첫 화면 전에 적용하고, `src/lib/theme.ts`가 전환·시스템 변경을 맡는다.
