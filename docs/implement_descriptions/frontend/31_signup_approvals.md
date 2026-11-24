# 31. FE-15a 회원 가입 승인

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` F60 (A31·A33·A82·F58·F59)
- 이전 기록: [30. FE-14a 운영진 틀](30_staff_shell.md)

## 배경
FE-15의 첫 PR이다(F60). 운영진이 자동 매칭(A31)에 실패한 수강생·멘토 가입을 승인하거나 반려한다. 승인할 때는 수강생은 명단 하나, 멘토는 계약 0개 이상을 연결한다(A33). 후보는 BE-3b(#127, A82)로 찾는다. '회원·권한' 모듈이 처음으로 레일에 들어간다.

Figma는 `Admin - 회원·권한` 데스크톱 Section의 `가입 승인 (FE-15a)`에 목록, 수강생 승인 창, 멘토 승인 창을 다듬었다(F58).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-approvals/api.ts` | 대기 목록(유형·기수, 20개씩), 대기 건수(탭·배지), 후보, 승인·반려(성공 시 목록·건수 다시 부름) |
| `features/admin-approvals/labels.ts` | 자동 매칭(명단 없음·계약 없음·후보 여러 명), 신청 기수, 일치 태그, 수강·계약 상태 |
| `features/admin-approvals/components/approvals-page.tsx` | 탭(수강생·멘토, 건수), 기수 필터(수강생 탭), 표, 빈 상태 |
| `features/admin-approvals/components/approval-dialogs.tsx` | 수강생 승인(검색 0.3초 지연, 후보 하나, 다른 기수·불일치 경고), 멘토 승인(계약 여러 개, 0개도 가능), 반려(사유 300자 필수), 오류 문구 |
| `features/staff/components/staff-cohort-select.tsx` | 운영진 기수 필터(담당 기수, A81) |
| `features/staff/nav.ts`, `components/staff-shell.tsx` | '회원·권한' 모듈과 '가입 승인' 메뉴(`user.approve` 또는 `contract.manage`), 대기 배지, 모듈 제목 |
| `components/ui/checkbox.tsx` | 체크박스(radix) |
| `routes/_staff/admin/members/approvals.tsx` | `?type=mentor`, `?cohort=` |
| `routes/_staff/admin/index.tsx` | 운영진 홈을 `admin.tsx`에서 옮겼다(하위 경로의 부모가 되지 않게) |

## 주요 결정 (사용자 결정, F60·A82)
- 탭 수강생·멘토, 기수 필터, 주소 `/admin/members/approvals`, 메뉴 배지. 후보는 백엔드 보완 API로 찾는다.

## 발견한 문제와 해결
- 운영진 홈 라우트 파일(`_staff/admin.tsx`)이 `/admin/...` 하위 경로의 부모가 되어 가입 승인 화면이 그려지지 않았다. `admin/index.tsx`로 옮겼다.

## 검증
- `lint`, `typecheck`, `format:check`, `build` 통과
- `vitest` 294 passed (TZ=UTC·America/Los_Angeles·Asia/Seoul). 새 테스트: 표시 함수, 목록(메뉴 배지·탭 건수·표·기수 필터), 수강생 승인(경고·검색·오류·성공), 멘토 승인(계약 선택), 반려(사유 필수), 빈 상태
- `playwright` 37 passed. 새 E2E: 메뉴 → 가입 승인 → 명단 골라 승인
- 1440 화면과 승인 창을 시안과 비교했다

## 남은 작업
- FE-15b 운영진 승인
