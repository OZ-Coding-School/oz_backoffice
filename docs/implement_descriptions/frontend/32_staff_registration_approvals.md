# 32. FE-15b 운영진 승인

- 상태: PR 진행 중
- 관련 PR: (작성 중)
- 관련 결정: `docs/decisions.md` F61 (A11·A12·A62·A63·A81·F26·F60)
- 이전 기록: [31. FE-15a 회원 가입 승인](31_signup_approvals.md)

## 배경
FE-15의 두 번째 PR이다(F60). 운영진이 처음 로그인해 입력한 소속·담당(FE-1c)을 최고 관리자·팀리드가 확인하고, 필요하면 고쳐 승인하거나 반려한다(A11·A12). 승인 API는 P3에서 만들어 두었고, 승인할 때 조정은 자유다(A62).

Figma는 `Admin - 회원·권한` 데스크톱 Section의 `운영진 승인 (FE-15b)`에 목록과 검토 창을 그렸다(F58).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/auth/staff-form.ts` | (FE-1c에서 나눔) 입력 규칙 `staffFormSchema`, 신청 값 → 폼 `staffFormValues`, 폼 → 본문 `staffPayload`(넓게 보면 부서 직속도 담당 가능) |
| `features/auth/components/staff-fields.tsx` | (FE-1c에서 나눔) 부서 → 팀 → 직위·고용 형태 → 담당 칸. `wide`면 모든 활성 과정과 넘겨받은 기수 |
| `features/auth/components/staff-registration-page.tsx` | 위 두 파일을 쓰도록 정리(동작 그대로) |
| `features/admin-staff-registrations/api.ts` | 신청 목록(상태별 20개씩), 대기 건수, 승인·반려, 이름표용 선택지(`withAllCohorts`), 넓게 볼 기수(`openCohorts`) |
| `features/admin-staff-registrations/components/registrations-page.tsx` | 탭(대기·승인·반려), 표, 처리한 신청은 읽기만 |
| `features/admin-staff-registrations/components/review-dialog.tsx` | 검토 창: 신청자 정보, 고칠 수 있는 폼, '다른 팀 과정도 보기', 승인 / 반려(사유 300자) |
| `routes/_staff/admin/members/staff-registrations.tsx` | `?status=approved|rejected` |
| `features/staff/nav.ts`, `components/staff-shell.tsx` | '운영진 승인' 메뉴(`role.assign`)와 대기 배지 |

- 신청 선택지의 기수는 조교가 없는 진행 예정·진행 중 기수뿐이라, 이름표에는 담당 기수(A81, 최고 관리자는 전체)를 더해 끝났거나 조교가 있는 기수도 이름이 보이게 했다.

## 주요 결정 (사용자 결정, F61)
- 대기·승인·반려 탭, 검토 창에서 조정, 신청 규칙 + '다른 팀 과정도 보기'.

## 검증
- `lint`, `typecheck`, `format:check`, `build` 통과
- `vitest` 299 passed (TZ=UTC·America/Los_Angeles·Asia/Seoul). 새 테스트: 선택지 합치기, 목록(메뉴 권한·배지·이름표·끝난 기수 이름), 검토(다른 팀 과정 추가 후 승인 본문), 반려, 반려 탭 읽기만. FE-1c 운영진 신청 테스트(41개)도 그대로 통과
- `playwright` 38 passed. 새 E2E: 메뉴 → 검토 → 승인
- 1440 목록과 검토 창을 시안과 비교했다

## 남은 작업
- FE-15c 직원·담당자
