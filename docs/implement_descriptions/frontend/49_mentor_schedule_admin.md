# 49. 멘토 일정 대리 (FE-18c-2)

- 상태: PR 진행 중
- 관련 PR: #171
- 관련 결정: `docs/decisions.md` F85·F87·F88·F89 (A37·A79·A106·A107, F51~F53)
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
| `features/mentor-schedule/components/schedule-page.tsx` (F88) | 요일 머리(오늘 원·주말 흐림)·[오늘]·오전/오후 시각 라벨·현재 시각 선·색 막대 블록(시각 + 이름)·빈 칸 마우스 "+ 시각" → 그 날짜·시각으로 추가 창 |
| `features/mentor-schedule/components/unavailable-dialogs.tsx` (F88) | 반복 세그먼트 → 요일 칩 → 시간(하루 종일 스위치) → 적용 기간 → 분류 칩(기타 직접 입력) → 메모, 요약 한 줄, 설명은 `?` |
| `features/mentor-schedule/form.ts` (F88) | 종료 날짜 없이 종료 시각이 시작과 같거나 이르면 다음 날, 하루 종일 마지막 날은 선택, 빈 칸 시각 기본값, `summaryOf` |
| `features/mentor-schedule/scope.ts` | `readOnly`(고칠 권한 없음: 조회만), `onMonth`(운영진 화면 주소로 달 이동) |
| `features/mentor-schedule/calendar.ts` (F89) | 날짜별 일정(`dayEvents`: 시각 회차는 시작한 날, 하루 종일은 걸친 날), 한 주 막대·줄 배치(`weekSegments`: 같은 개인 일정은 이어서, 3줄 넘으면 칸마다 숨은 수) |
| `features/mentor-schedule/api.ts` (F89) | 달력 6주 세션(`monthSessionsQueryOf`, 100건씩 끝까지), 참고용 휴일(`holidaysQuery`, A107) |
| `features/mentor-schedule/components/schedule-page.tsx` (F89) | 월 달력(머리 [오늘]·‹ ›·범례, 이어진 막대, '+N개' 팝오버, 공휴일 빨강), 휴대폰 작은 달력 + 고른 날 목록, 목록 항목 누르면 상세 |
| `features/mentor-schedule/components/unavailable-dialogs.tsx` (F89) | `UnavailablePanel`: 상세(F68 섹션, [수정][삭제])·추가·수정 슬라이드 패널, 충돌 확인·삭제 확인 창은 그대로 |
| 라우트 | `/mentor/schedule?month=`, 운영진 `?tab=schedule&month=` |

## 주요 결정 (사용자 결정, F85·F87·A106)
- 멘토 일정 화면 재사용, 시간표에 세션까지 보이도록 백엔드를 먼저 보완.
- 화면 확인 중 배치 정리(멘토 본인 일정에도 적용): 신청 받기는 오른쪽 열 맨 위, 불가 시간 추가는 섹션 제목 옆 `+` 아이콘, 항목 수정·삭제는 아이콘 버튼.
- 시간표·불가 시간 창 개편(F88, 멘토 본인 일정에도 적용, 이후 F89로 달력·패널로 바뀜): 시각 라벨·블록·오늘·현재 시각 표시, 빈 칸을 눌러 바로 추가, 창은 질문 순서로 다시 배치하고 요약 한 줄·적용 기간·분류 칩만. 화면 이름은 '불가 시간' 대신 '개인 일정'(분류 칩 '개인 일정'은 그대로), 블록 바탕은 더 짙은 파스텔, 이웃한 날의 같은 반복 일정은 한 덩어리로 이어 그림. Figma `Screen / 일정 · 데스크톱 (F88 개편)`·`Screen / 불가 시간 추가 · 데스크톱 (F88 개편)`.

- 월 달력·슬라이드 패널(F89): 달 기준 달력은 조회만, 반복 개인 일정은 이어진 막대, 색은 공휴일 빨강·개인 일정 파랑·멘토링 보라, 공휴일은 참고용(백엔드 BE-3z #172, A107), 개인 일정 상세·추가·수정은 슬라이드 패널, 휴대폰은 작은 달력 + 고른 날 목록. Figma `Screen / 일정 · 데스크톱 (월 달력)`·`(개인 일정 상세 패널)`·`(개인 일정 추가 패널)`·`Screen / 일정 · 모바일 (월 달력)`·`Example / 12월 공휴일`.

## 발견한 문제와 해결
- 운영진 화면에는 세션 상세가 아직 없어 시간표 세션 블록을 링크 없이 보여 준다.
- 1440에서 요일 칸이 좁아 "09:00–12:00"이 잘려, 블록 시각은 시의 앞 0을 빼고(9:00–12:00) 11px로 줄였다.
- 프로젝트 테마가 Tailwind 기본 색(`--color-*: initial`)을 지워 `bg-red-100`이 만들어지지 않아, 블록 바탕은 값을 직접 지정했다.
- 종료 날짜 입력을 없애 자정을 넘는 시간은 종료 시각이 시작보다 이르면 다음 날로 본다(24시간을 넘는 입력이 생기지 않음).

- 운영진 화면은 `<fieldset disabled>`로 막던 방식이 달 이동 버튼까지 막아, 스코프의 `readOnly`로 [+]·신청 받기만 막고 수정·삭제는 숨기게 바꿨다.
- 6주 달력의 세션이 100건을 넘을 수 있어 목록을 100건씩 끝까지 받는다.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul, 411개), `build`, `e2e`(49개)
- F88 개편 후 1440·390 화면(시간표·빈 칸 마우스·수정 창) 확인
- F89 월 달력: `test`(UTC·Asia/Seoul, 414개), `e2e`(49개), 1440 라이트·다크·상세·수정 패널, 768, 390·추가 패널 화면 확인
- 개발 DB 목데이터(F89): 법정공휴일 12/25 기독탄신일·1/1, 추가 휴일 12/24 학원 휴무
- 1440 라이트·다크 화면 확인
- 개발 DB 목데이터: 멘토1 불가 시간 3건(매주 회사 근무·매일 휴식·11/27 한 번), 기존 세션 1건

## 남은 작업
- FE-19 이후 운영진 화면.
