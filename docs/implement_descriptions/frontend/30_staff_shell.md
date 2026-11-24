# 30. FE-14a 운영진 틀

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` F59 (F3·F15·F17·F58·A81)
- 이전 기록: [29. FE-13 멘토 홈](29_mentor_home.md)

## 배경
운영진 화면(FE-14~23)의 첫 PR이다. 지금까지 운영진은 로그인하면 임시 홈(F20)만 보였다. 운영진 화면이 들어갈 틀을 만든다. 틀에는 모듈 레일, 모듈 메뉴, 상단 막대, 사용자 메뉴가 있다. 메뉴는 BE-3(`GET /me/staff-access`, A81)의 권한으로 숨긴다.

운영진 화면은 데스크톱(1440)만 지원하고, Figma는 PR마다 그 화면만 다듬는다(F58).
- Figma `Admin - 홈` 데스크톱 Section: `운영진 틀 (FE-14a)`(홈, 사용자 메뉴 열림). 다른 운영진 페이지의 태블릿·모바일 자리 문구는 'F58: 그리지 않음'으로 바꿨다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/staff/api.ts` | `staffAccessQuery`(5분 유지), `hasPermission` |
| `features/staff/nav.ts` | 모듈·메뉴 정의(지금은 홈만), `staffModules`(권한으로 거르고 빈 모듈 제외), `currentStaffNav`(가장 길게 맞는 메뉴) |
| `features/staff/labels.ts` | `roleLines`: 전체 범위는 역할 이름, 과정·기수 범위는 담당 기수 목록에서 이름을 찾아 앞에 붙인다 |
| `features/staff/components/staff-shell.tsx` | 모듈 레일 · 모듈 메뉴 · 상단 막대(위치·테마) · 사용자 메뉴(오른쪽으로 열림). 최소 폭 1280 |
| `features/staff/components/staff-home.tsx` | 인사말 + 요약 자리(FE-14b) / 권한 없음 안내 |
| `routes/_staff.tsx`, `routes/_staff/admin.tsx` | 틀을 그리기 전에 권한을 받아 둔다(`ensureQueryData`) |
| `features/auth/components/temp-home.tsx` | 삭제(쓰는 곳 없음) |

- 레일·메뉴 링크는 라우터의 자동 활성 표시를 정확히 같을 때만 쓰고, 하위 경로의 활성은 `currentStaffNav`로 정한다. 하위 화면이 생겨도 '홈'이 활성으로 보이지 않게 하려는 것이다.

## 주요 결정 (사용자 결정, F58·F59)
- PR마다 Figma, 데스크톱만. 14a 틀 → 14b 홈. 메뉴는 만든 화면만. 현재 기수 선택은 첫 기수 화면 PR에서. 검색·알림 제외.

## 검증
- `lint`, `typecheck`, `format:check`, `build` 통과
- `vitest` 288 passed (TZ=UTC·America/Los_Angeles·Asia/Seoul). 새 테스트: 권한 거르기·현재 메뉴·역할 줄, 틀(레일·메뉴·위치·사용자 메뉴), 권한 없음 안내, 로그아웃. 임시 홈을 보던 로그인·운영진 테스트는 운영진 홈 제목으로 바꿨다
- `playwright` 36 passed. 새 E2E: 운영진 틀과 사용자 메뉴의 역할
- 1440 화면을 시안과 비교했다

## 남은 작업
- FE-14b 운영진 홈(처리할 일 요약)
