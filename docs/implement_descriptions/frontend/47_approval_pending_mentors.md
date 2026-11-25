# 47. 가입 승인 멘토 탭: 가입 전 멘토 고르기 (FE-15a 보완)

- 상태: PR 진행 중
- 관련 PR: #167
- 관련 결정: `docs/decisions.md` F84 (A105, F66)
- 이전 기록: [46. 행정 업무 > 계약 (FE-18b)](46_admin_contracts.md), [31. 회원 가입 승인 (FE-15a)](31_signup_approvals.md)

## 배경
멘토 계약은 이제 항상 가입 전 멘토에 속한다(A104). 자동 연결이 안 된 멘토 가입은 운영진이 가입 전 멘토를 골라 연결한다(A105).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-approvals/components/approval-dialogs.tsx` | 멘토 승인 창: 가입 전 멘토 후보(이름·휴대폰·계약 n건·일치 태그·가입 전 배지) 하나 고르기, '이 멘토에 연결하고 승인'(`mentor_id`) / '새 멘토로 승인', 고른 멘토 빼기 |
| `features/admin-approvals/api.ts`, `labels.ts` | 승인 요청 `mentor_id`, 자동 매칭 결과 '가입 전 멘토 없음', 쓰지 않는 계약 상태 표시 정리 |
| `approvals.test.tsx` | 가입 전 멘토를 골라 승인 |

## 주요 결정 (사용자 결정, F84)
- 후보는 가입 전 멘토만, 하나 고르기. 예전 미연결 계약은 보여 주지 않는다.

## 발견한 문제와 해결
- 없음

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul, 398개), `build`, `e2e`(49개)
- 1440 라이트·다크 승인 창 확인

## 남은 작업
- FE-18c 기수 배정·일정 대리.
