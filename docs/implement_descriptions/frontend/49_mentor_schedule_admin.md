# 49. 멘토 일정 대리 (FE-18c-2)

- 상태: PR 진행 중
- 관련 PR: #171
- 관련 결정: `docs/decisions.md` F85·F87 (A37·A79·A106, F51~F53)
- 이전 기록: [48. 멘토 기수 배정 관리 (FE-18c-1)](48_mentor_assignments.md)

## 배경
운영진이 멘토 대신 불가 시간과 신청 받기를 관리한다(F85). 멘토 일정 화면(FE-11)을 그대로 쓰고 운영진 API로 바꿔 부른다. 시간표의 세션은 BE-3y(A106)로 가져온다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/mentor-schedule/scope.ts` | 일정 화면의 대상(`mentorId`)·주 이동(`onWeek`) 컨텍스트. 기본은 멘토 본인 |
| `features/mentor-schedule/api.ts` | `scheduleQueryOf`·`weekSessionsQueryOf`, 신청 받기·불가 시간 저장·삭제가 대상 멘토면 운영진 API(`/admin/mentors/{id}/schedule*`, `/sessions`) |
| `features/mentor-schedule/components/*` | 컨텍스트를 따라 조회·저장, `embedded`면 제목 없이 운영진 문구, 운영진 화면의 세션 블록은 링크 없이 |
| `features/admin-mentors/components/mentor-page.tsx`, 라우트 | 멘토 상세 '일정' 탭(가입한 멘토만, `?tab=schedule&week=`), 멘토 관리 권한이 없으면 입력을 막음 |
| `features/admin-mentors/schedule.test.tsx` | 운영진 API 조회·삭제·주 이동·신청 받기·권한 없음 |

## 주요 결정 (사용자 결정, F85·F87·A106)
- 멘토 일정 화면 재사용, 시간표에 세션까지 보이도록 백엔드를 먼저 보완.
- 화면 확인 중 배치 정리(멘토 본인 일정에도 적용): 신청 받기는 오른쪽 열 맨 위, 불가 시간 추가는 섹션 제목 옆 `+` 아이콘, 항목 수정·삭제는 아이콘 버튼.

## 발견한 문제와 해결
- 운영진 화면에는 세션 상세가 아직 없어 시간표 세션 블록을 링크 없이 보여 준다.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul, 406개), `build`, `e2e`(49개)
- 1440 라이트·다크 화면 확인
- 개발 DB 목데이터: 멘토1 불가 시간 3건(매주 회사 근무·매일 휴식·11/27 한 번), 기존 세션 1건

## 남은 작업
- FE-19 이후 운영진 화면.
