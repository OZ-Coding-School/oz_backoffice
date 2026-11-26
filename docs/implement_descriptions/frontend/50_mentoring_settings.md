# 50. 멘토링 > 멘토링 설정 (FE-19a)

- 상태: PR 진행 중
- 관련 PR: #173
- 관련 결정: `docs/decisions.md` F90 (F59·F68·F86, A34·A37)
- 이전 기록: [49. 멘토 일정 대리 (FE-18c-2)](49_mentor_schedule_admin.md)

## 배경
FE-19(멘토링 설정·팀)의 첫 PR이다(F90: 19a 설정 → 19b 팀 관리 → 19c 팀 상세). 멘토링 모듈의 첫 기수 단위 화면이라 상단 막대의 현재 기수 선택기(F59)도 이번에 붙인다. 백엔드 API(`…/mentoring-settings`, `…/mentoring-block-times`)는 이미 있다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/staff/nav.ts` | 레일 '멘토링' 모듈 · '멘토링 설정' 메뉴(`mentoring.settings.read`), 메뉴 `match`로 기수 단위 주소를 그 메뉴로 본다 |
| `features/staff/current-cohort.ts` | 주소의 기수 id, 선택기 목록(보관 제외), 마지막 기수 기억(localStorage), 처음 기수(기억 → 진행 중 첫 기수 → 첫 기수) |
| `features/staff/components/cohort-picker.tsx` | 상단 막대 현재 기수 선택기: 검색·과정별 묶음·상태 배지, 고르면 같은 화면의 그 기수 주소로 |
| `features/staff/api.ts` | `hasPermissionIn`: 권한이 이 기수에 미치는가(최고 관리자·전체·과정·기수 범위) |
| `features/admin-mentoring/api.ts`, `form.ts` | 금지 시간대 조회·추가·수정·삭제, 설정 저장, 설정·금지 시간대 입력 스키마(시간 단위 지급 ↔ 분, 운영시간 끝 24:00) |
| `features/admin-mentoring/components/settings-page.tsx` | 기본 규칙(스위치·세그먼트)·운영시간(운영 스위치 + 시각)·[저장](바뀐 것이 있을 때, 처음이면 기본값 그대로도)·떠날 때 확인, 아직 저장하지 않은 기수 안내 |
| `features/admin-mentoring/components/block-time-sheet.tsx` | 금지 시간대 패널(F68): 조회([수정][삭제]) · 추가 · 수정, 삭제 확인 |
| 라우트 | `/admin/mentoring/settings`(현재 기수로 보냄, 기수가 없으면 안내), `/admin/cohorts/$cohortId/mentoring/settings` |

## 주요 결정 (사용자 결정, F90)
- PR은 19a 설정 → 19b 팀 관리 → 19c 팀 상세.
- 현재 기수 선택기는 담당 기수, 전체 권한은 보관 제외 모든 기수(`/me/staff-access`가 이미 이렇게 준다). 과정별·진행 중 먼저·검색, 처음엔 진행 중인 첫 기수.
- 휴일 카드는 빼고 운영시간 '주말·공휴일' 줄의 `?`와 '공휴일 보기' 바로가기만.
- 금지 시간대는 맨 위 점선 추가 카드 + 슬라이드 패널.

## 발견한 문제와 해결
- 금지 시간대 패널(포털)이 설정 `<form>` 안에 있으면 React 제출 이벤트가 포털을 지나 설정 폼까지 올라가, 폼은 왼쪽 열만 감싸고 [저장]은 `form` 속성으로 연결했다.
- 세그먼트 버튼을 `w-fit`으로 두면 칸이 줄어 글자가 줄바꿈되어 선택지 수에 맞춘 폭을 준다.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul 420개), `build`, `e2e`(50개)
- 1440 라이트·다크, 기수 선택기 펼침, 금지 시간대 추가 패널 화면 확인
- 개발 DB 목데이터: 헬스케어 8기 금지 시간대 2건 추가(12월 19~21시 프로젝트 발표 준비, 2/15~2/28 09~18시 사유 없음, 기존 1건과 함께 3건). 설정이 없는 기수(예: BX 4기)는 '아직 저장하지 않은 기수' 상태

## 남은 작업
- 19b 팀 관리, 19c 팀 상세.
