# 33. FE-15c 직원·담당자

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` F62 (A17·A36·A62·A83·F58)
- 이전 기록: [32. FE-15b 운영진 승인](32_staff_registration_approvals.md)

## 배경
FE-15의 세 번째 PR이다(F60). 직원의 소속(부서·팀·직위·고용 형태)을 관리하고, 과정·기수 담당자(운영 매니저·조교)를 배정·해제한다. 담당자를 바꾸면 그 직원의 범위 역할도 함께 바뀐다(A17). 앞선 BE-3c(#130, A83)가 직원 목록에 검색·팀 필터·담당을 더하고 조회 권한을 `staff.assign`까지 넓혔다.

Figma는 `Admin - 회원·권한` 데스크톱 Section의 `직원·담당자 (FE-15c)`에 직원 탭, 담당자 탭, 담당자 추가 창, 소속 수정 창을 그렸다(F58).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-staff/api.ts` | 직원 목록(검색·부서·팀, 20개씩)·직원 찾기, 과정·기수 담당자 조회·추가·해제, 소속 수정, 담당 요약 |
| `features/admin-staff/components/staff-page.tsx` | 탭(권한 있는 것만), 직원 탭(검색어는 입력이 멈추면 주소에 반영, 부서·팀 필터, [수정]은 `org.manage`만), 담당자 탭(과정 필수·기수 선택, 목록·[담당자 추가]) |
| `features/admin-staff/components/staff-dialogs.tsx` | 소속 수정(공용 폼, 담당 칸 없이), 담당자 추가(직원 찾기·'담당 중' 막기·역할, 기수면 조교 기본), 해제 확인 |
| `features/auth/components/staff-fields.tsx` | `withAssignments` 옵션(담당 칸 숨김) |
| `lib/use-debounced.ts` | 검색 입력 지연(가입 승인 창과 함께 씀) |
| `routes/_staff/admin/members/staff.tsx` | `?tab=staff&q=&department=&team=&bootcamp=&cohort=` |
| `features/staff/nav.ts` | '직원·담당자' 메뉴(`org.manage` 또는 `staff.assign`) |

## 주요 결정 (사용자 결정, F62·A83)
- 한 메뉴에 직원·담당자 탭, 권한 있는 탭만. 직원 조회는 `staff.assign`도 허용, 수정은 `org.manage`만.

## 검증
- `lint`, `typecheck`, `format:check`, `build` 통과
- `vitest` 303 passed (TZ=UTC·America/Los_Angeles·Asia/Seoul). 새 테스트: 담당 요약, 직원 탭(검색·소속 수정 본문), 담당자 탭(목록·'담당 중' 막기·추가·해제), 권한별 탭·수정 버튼
- `playwright` 39 passed. 새 E2E: 담당자 탭에서 과정·기수 고르고 조교 추가
- 1440 직원 탭·담당자 탭·추가 창을 시안과 비교했다

## 남은 작업
- FE-15d 역할·권한
