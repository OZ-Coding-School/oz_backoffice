# Frontend

OZ 통합 백오피스 프론트엔드. `apps/backend`의 REST API를 사용하는 SPA.

## 기술 스택

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| UI 라이브러리 | React | 컴포넌트 기반 UI |
| 빌드/개발 서버 | Vite | 번들링, HMR, 환경변수(`VITE_*`) |
| 언어 | TypeScript | 정적 타입 (strict 모드) |
| 스타일 | Tailwind CSS | 유틸리티 클래스 기반 스타일링 |
| UI 컴포넌트 | shadcn/ui | Radix 기반 컴포넌트 (소스 복사 방식, `components/ui`) |
| 서버 상태 | TanStack Query | API 조회/캐싱/뮤테이션, 서버 데이터의 단일 출처 |
| 클라이언트 상태 | Zustand | 인증 세션, UI 상태 등 서버와 무관한 전역 상태 |
| 아이콘 | lucide-react | 아이콘 세트 |
| 린트 | oxlint | 정적 분석 |

## 테스트

처음부터 아래 테스트 구성을 함께 적용한다.

| 영역 | 기술 | 용도 |
| --- | --- | --- |
| 단위/컴포넌트 테스트 러너 | Vitest | 테스트 실행, jsdom 환경 |
| 컴포넌트 테스트 | Testing Library | 사용자 관점의 렌더링/상호작용 검증 |
| API 모킹 | MSW | 테스트와 로컬 개발에서 백엔드 API 응답 모킹 |
| E2E | Playwright | 실제 브라우저 기반 사용자 시나리오 검증 |

## 상태 관리 원칙

- 서버에서 온 데이터는 TanStack Query로만 관리한다. Zustand에 복사해 두지 않는다.
- Zustand는 클라이언트 전용 상태(로그인 세션 정보, 사이드바, 필터 UI 등)에만 사용한다.
