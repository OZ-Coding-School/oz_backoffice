# 35. 회원 관리·가입 승인 통합 (FE-15e)

- 상태: PR 진행 중
- 관련 PR: #138
- 관련 결정: `docs/decisions.md` F64·F66
- 이전 기록: [34. 조직 설정 > 권한 (FE-15d)](34_org_permissions.md)

## 배경
메뉴 개편(F64)에서 '회원·권한' 모듈을 '회원 관리'로 바꾸고, 따로 있던 '가입 승인'(수강생·멘토)과 '운영진 승인'을 한 메뉴로 합치기로 했다. 메뉴 개편은 PR 두 개로 나눴고(F66), 이번 PR은 그 첫 번째다. 직원 메뉴를 조직 설정으로 옮기는 작업은 다음 PR(15f)에서 한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-approvals/tabs.ts` | 가입 유형 탭 3개(수강생 `member.approval.read` · 멘토·강사 `educator.contract.read` · 운영진 `staff.registration.read`)와 권한별 탭 고르기 |
| `features/admin-approvals/components/approvals-page.tsx` | '가입 승인' 머리, 권한 있는 탭만·대기 건수 표시, 수강생 탭에 기수 선택, 운영진 탭은 운영진 승인 패널을 보여 줌 |
| `features/admin-staff-registrations/components/registrations-page.tsx` | 독립 화면 → 운영진 탭 안의 패널(`RegistrationsPanel`). 제목을 없애고 대기·승인·반려를 세그먼트로 고름 |
| `routes/_staff/admin/members/approvals.tsx` | `/admin/members/approvals?tab=mentor|staff&cohort=&status=approved|rejected` (탭이 없으면 수강생), 운영진 선택지 미리 불러오기 |
| `routes/_staff/admin/members/staff-registrations.tsx` | 삭제 (운영 배포 전이라 옛 주소를 남기지 않음, F66) |
| `features/staff/nav.ts`, `components/staff-shell.tsx` | 모듈 이름 '회원 관리', 운영진 승인 메뉴 삭제, 가입 승인 배지는 회원 가입 대기 + 운영진 신청 대기의 합 |

## 주요 결정 (사용자 결정, F66)
- 메뉴 개편은 PR 두 개(15e 가입 승인 통합, 15f 조직 설정 > 직원).
- 탭은 수강생 · 멘토·강사 · 운영진. 탭 이름은 '직원' 대신 '운영진'(시안 확인 때 변경).
- 주소는 `/admin/members/approvals?tab=`, 예전 운영진 승인 주소는 바로 없앤다.

## 발견한 문제와 해결
- 화면 파일에서 탭 정의를 함께 내보내 oxlint(react-refresh) 경고가 났다 → 탭 정의를 `tabs.ts`로 분리.

## 검증
- `lint`, `format:check`, `typecheck` 통과
- `vitest` 313 passed (UTC·Asia/Seoul). 바꾼 테스트: 멘토·강사 탭 이름·주소, 운영진 탭(메뉴 배지 합·권한 없는 탭 숨김·대기 상태·검토·승인·반려·반려 탭 읽기만)
- `build`, Playwright E2E 40 passed (레일 '회원' → 가입 승인 운영진 탭 → 검토 → 승인)
- 1440 화면 확인(수강생 탭, 운영진 탭)

## 남은 작업
- 15f 조직 설정 > 직원(부서·팀별 목록, 오른쪽 상세 패널), 기존 직원·담당자 메뉴 삭제
- 부서·직위 메뉴, BE-3i 전체 회원 API, 15g 전체 회원
