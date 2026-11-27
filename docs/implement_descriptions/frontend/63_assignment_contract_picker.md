# 63. 배정 패널에서 근거 계약 고르기 (F98)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` F98 (A110·A115, F85)
- 이전 기록: [62. 계약 화면: 새 사람의 멘토는 계약 완료 때](62_contract_mentor_on_sign.md), 백엔드 [109](../backend/109_assignment_contract_basis.md)

## 배경
BE-4b(#187)로 기수 배정은 근거 계약이 필수가 됐지만 배정 패널에 계약을 고르는 칸이 없어 develop에서 배정 추가가 막혀 있었다.

## 구현 내용
- `features/admin-mentors/assignment-api.ts`: 근거 계약 후보 조회 `contractCandidatesQuery`(`GET /admin/cohorts/{id}/mentor-assignments/contract-candidates?mentor_id=`), 근거 계약 오류 문구.
- `components/contract-picker.tsx`: 후보 라디오 카드(명칭·상태 배지·기수 계약/과정 공통·기간·단가·노쇼), 하나면 미리 고름, 없으면 안내와 계약 화면 링크.
- `components/assignment-sheet.tsx`: 배정 추가는 기수를 고르면 근거 계약 섹션, 계약을 고르면 기간을 계약·기수에 맞춰 채우고 정산 조건을 보여 준다. [수정]에서도 근거 계약을 바꿀 수 있다(바꾼 경우만 `contract_id`). 단가 기준 문구 '회당'.
- 테스트: 수정에서 다른 계약으로 바꿔 저장, 추가에서 후보 하나 미리 고름·기간 채움.

## 검증
- lint, format:check, typecheck, vitest 430개(UTC·Asia/Seoul), build, e2e 51개 통과.

## 확인용 데이터
- 개발 DB: 강사·멘토 › 멘토 › '새로운멘토' › 배정 탭의 헬스케어 8기 배정 [수정] — 후보 두 개(8기 멘토 계약 이행 중, 8기 겨울 특강 계약 완료). '멘토1'로 배정 추가 → 헬스케어의 다른 기수를 고르면 과정 공통 계약(이행 중)이 후보로 나온다.

## 남은 작업
- 계약 화면 Figma 반영, FE-19c 팀 상세.
