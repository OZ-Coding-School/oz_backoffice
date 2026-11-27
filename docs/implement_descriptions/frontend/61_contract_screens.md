# 61. 행정 업무 › 계약 개편 화면 (F96)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` F96 (A109·A110·A111·A112, F83·F94)
- 이전 기록: [60. 두 칸 기수 선택기를 수강생·가입 승인에도](60_cohort_chooser_reuse.md), 백엔드 [108](../backend/108_contract_redesign.md)·[109](../backend/109_assignment_contract_basis.md)·[110](../backend/110_contract_list_counts.md)

## 배경
계약 구조가 바뀌었다(A109: 종류 5개, 과정 필수·기수 선택, 상태 7개, 정산 유형·금액, 서명 후 변경 계약). BE-4a·4b·4c가 병합됐지만 계약 화면은 컴파일만 맞춘 상태라 [계약 추가]가 막혀 있었다. 사용자와 정한 화면 구성(F96)으로 계약 화면을 다시 만든다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/staff/components/cohort-picker.tsx` | `CohortChooser`에 '과정 전체' 줄(`bootcampValue`·`onPickBootcamp`)과 `remember`(현재 기수로 기억하지 않고 최근 목록에만). 상단 막대용 `AdminScopePicker`(행정 업무 주소에서만, `?bootcamp=&cohort=`) |
| `features/staff/current-cohort.ts` | `pushRecentCohort`, 행정 업무 선택 기억 `rememberedAdminScope`·`rememberAdminScope`(멘토링 현재 기수와 따로) |
| `features/staff/components/staff-shell.tsx` | 상단 막대에 `AdminScopePicker` |
| `routes/_staff/admin/administration/contracts.tsx` | 검색 파라미터 `bootcamp`·`cohort`·`status`(open·closed·all)·`type`·`q`·`contract` |
| `features/admin-contracts/api.ts` | 상태 묶음, 목록(기수면 `include_bootcamp_common`), 변경 이력·변경 계약서 주소, 추가(+진행 시작)·수정·변경 등록·진행/완료/종료·취소·해지·삭제·옮기기 훅 |
| `features/admin-contracts/labels.ts` | 상태·종류·정산 유형·단가 기준·부가세·정산 시간·해지 사유 문구, 금액·과정 / 기수·기간 표시, 변경 항목 이름, 오류 문구 |
| `features/admin-contracts/contract-values.ts` | 위저드·수정·변경 등록이 함께 쓰는 Zod 스키마(종류별 필수 칸), 추가·수정(바뀐 항목)·변경 계약(바꿀 수 있는 항목) 본문 |
| `components/contracts-page.tsx` | 머리(범위 칩·건수·[계약 추가]), 종류 탭 + 건수, 상태 선택, 검색, 표(계약 명칭·종류·이름 또는 업체명·과정 / 기수·기간·금액·상태·담당) |
| `components/contract-wizard.tsx` | 계약 추가 위저드 5단계(단계 표시, 단계마다 검사, 확인 요약, [초안으로 저장]·[진행 시작]) |
| `components/contract-fields.tsx` | 종류·과정 / 기수·명칭, 이름 또는 업체명(기존 멘토 검색·새 사람·업체 칸), 금액(정산 유형별 칸), 기간 섹션 |
| `components/contract-sheet.tsx` | 조회 패널: 상태 단계·다음 단계 버튼, [수정]/[변경 등록] + ⋯(취소·해지·삭제), 계약 정보·금액·이름 또는 업체명·계약서 · 담당·취소/해지·변경 이력 |
| `components/contract-form.tsx` | 같은 패널의 편집 모드: 수정(초안·진행 중)·변경 등록(변경 일자·사유·변경 계약서) |
| `components/dialogs.tsx` | 다음 단계·취소·해지·삭제·담당 직원 변경 확인 창 |
| `components/file-picker.tsx` | 계약서 PDF 고르기(바로 올림) |
| `features/admin-mentors/components/mentor-page.tsx` | 멘토 상세 '계약' 탭 카드에 과정 / 기수·단가, 취소도 끝난 계약으로 |
| 테스트 | `contracts.test.tsx`(목록·범위·탭·상태·권한, 위저드 멘토/업체, 패널 변경 등록·해지·진행·취소·수정·계약 완료), `mentors.test.tsx`, `e2e/admin-contracts.spec.ts` |

## 주요 결정
- F96(사용자 결정): 상단 과정·기수 선택기, 종류 탭 + 건수, 상태 묶음, 위저드, 상태 단계 패널, 변경 등록, ⋯ 메뉴, 문구('이름 또는 업체명', '과정 / 기수').
- F96에 없던 세부는 기존 패턴으로 정했다(사용자 확인 필요):
  - 수정 모드에서 **종류는 바꾸지 않는다**(멘토 계약은 멘토에 속하고 종류가 바뀌면 칸이 크게 달라져서. 다른 종류면 삭제·취소 후 새로).
  - 처음 범위: 이 화면에서 마지막으로 고른 과정·기수 → 진행 중인 첫 기수 → 첫 기수. 볼 수 있는 기수가 없으면 범위 없이 전체.
  - 기존 멘토를 고르면 이름·휴대폰·이메일을 그 멘토 정보로 채운다. 멘토 조회 권한이 없으면 '새 사람'만.
  - [진행 시작]은 계약서가 있어야 누를 수 있고, 저장은 됐는데 진행 시작이 실패하면 초안으로 두고 경고 토스트.
  - 진행 중 계약은 계약서를 뺄 수 없고(바꾸기만), 금액 입력은 쉼표를 자동으로 넣는다(20억까지).
  - 해지 사유 기본값은 '합의', 취소·해지 일자 기본값은 오늘.
  - 상태 단계에서 취소·해지가 어느 단계에서 멈췄는지는 응답에 없어 계약서 유무(취소)·해지 일자와 시작일(해지)로 표시한다.
  - 패널 너비: 조회 560px, 위저드 640px.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(429개, `TZ=UTC`·`Asia/Seoul`), `build`, `e2e`(51개) 통과.
- 1440 화면 캡처로 목록·상단 선택기·위저드 단계·조회 패널(라이트·다크)·변경 등록·업체 계약 패널·취소 창 확인.

## 남은 작업
- 사용자 로컬 확인 후 병합, 실제 화면으로 Figma 시안 갱신.
- 배정 패널에서 근거 계약 고르기(A110 화면 PR).
