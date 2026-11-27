# 59. 멘토링 > 팀 관리 (FE-19b)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` F93·A108 (F90·F91·F92, A39·A40)
- 이전 기록: [58. 디자인 다듬기 ⑧ 멘토 화면](58_design_refresh_mentor.md)

## 배경
FE-19의 두 번째 PR(F90). 현재 기수의 팀 목록·팀 만들기·팀 시간 일괄 지급. 팀 상세(팀원 넣고 빼기·수정·삭제·계좌·채팅·신청·세션)는 19c. 목록의 신청·세션 수는 백엔드 보완(BE-3z2 #183, A108)으로 받는다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/staff/nav.ts`, 라우트 | '멘토링 › 팀 관리' `/admin/mentoring/teams` → `/admin/cohorts/{id}/mentoring/teams`(현재 기수) |
| `features/admin-mentoring/teams-api.ts` | 팀 목록(집계 포함)·팀 없는 수강생·기수 배정 멘토, 팀 만들기, 팀 시간 지급(Idempotency-Key는 창을 열 때 한 번) |
| `components/teams-page.tsx` | 머리(팀 N개 · 팀원 M명, [전체 팀 지급][팀 만들기]), 팀 없는 수강생 안내, 표(팀·담당 멘토·팀원·잔여·대기 신청·세션 예정·완료), 체크 → 떠오르는 막대, 팀 멘토링을 받지 않는 기수 안내 |
| `components/create-team-sheet.tsx` | 팀 만들기 패널(F68): 이름(선택)·담당 멘토(활성 배정)·팀원(팀 없는 수강 중 수강생 체크) |
| `components/grant-teams-sheet.tsx` | 팀 시간 지급 패널: 시간(비우면 기수 기본)·사용 기간(새 계좌만)·사유 필수, 결과(지급·건너뜀 사유) |
| `components/empty-state.tsx` | 설명에 링크를 넣을 수 있게 |

## 주요 결정 (사용자 결정, F93·A108)
- 신청·세션 수는 백엔드 보완 후 표시.
- 행은 팀 상세(19c)로, 19b에서는 팀 만들기만 패널. 19c 전까지 행은 누를 수 없다.
- 일괄 지급은 체크 → 떠오르는 막대 → 패널, 전체 팀 지급은 머리 버튼.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul 425개), `build`, `e2e`(51개)
- 1440 화면(목록·지급 패널 결과) 확인
- 개발 DB 목데이터: 헬스케어 8기 팀 3개(알파 4명·2팀 3명(새로운멘토)·베타 2명), 팀 없는 수강 중 수강생 20명(안내 표시), 계좌는 비워 둠(화면에서 지급해 보기)

## 남은 작업
- 19c 팀 상세, Figma 반영.
