# 60. 두 칸 기수 선택기를 수강생·가입 승인에도 (F95)

- 상태: PR 진행 중
- 관련 PR: #185
- 관련 결정: `docs/decisions.md` F94·F95
- 이전 기록: [59. 멘토링 > 팀 관리](59_mentoring_teams.md)

## 배경
FE-19b PR에서 상단 막대의 현재 기수 선택기를 두 칸(과정 | 기수)·검색·최근 3개·종료 기수 스위치로 바꿨다(F94). 사용자가 기수를 고르는 다른 메뉴에도 같은 선택기를 쓰자고 했고, 적용할 메뉴로 **학사 › 수강생**과 **회원 관리 › 가입 승인**을 골랐다(F95).

## 구현 내용
- `features/staff/components/cohort-picker.tsx`: 선택기 본체를 `CohortChooser({cohorts, value, onPick, variant: "bar" | "field", label, allLabel?})`로 뺐다. `bar`는 상단 막대 모양, `field`는 필터 줄에 놓는 입력칸 모양(`aria-label`은 `label`). `allLabel`을 주면 검색 아래에 '전체 기수' 칩이 생기고 고르면 `onPick(null)`. 상단 막대 `CohortPicker`는 이 부품을 `bar`로 쓴다. 고른 기수는 최근 목록(`oz.admin.recent-cohorts`)과 마지막 기수 기억에 함께 남는다.
- `features/admin-students/components/students-page.tsx`: 과정·기수 Select 두 개를 `CohortChooser`(필드형, '기수')로 바꿨다. 고르면 `?cohort=`만 바꾸고 묶어 보기는 유지한다.
- `features/admin-approvals/components/approvals-page.tsx`: `StaffCohortSelect`를 `CohortChooser`(필드형, '전체 기수' 칩)로 바꿨다. '전체 기수'면 `?cohort=`를 지운다.
- `features/staff/components/staff-cohort-select.tsx` 삭제(쓰는 곳 없음).
- 테스트: 수강생·가입 승인 컴포넌트 테스트를 새 선택기 조작(과정 고르기 → 기수 고르기, '전체 기수' 눌림 상태)으로 바꿨다.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(426개, `TZ=UTC`·`Asia/Seoul` 둘 다), `build`, `e2e`(51개) 통과.
- 1440 화면 캡처로 두 화면의 펼친 선택기 확인(수강생: 현재 기수 체크, 가입 승인: '전체 기수' 칩).

## 남은 작업
- FE-19c 팀 상세.
