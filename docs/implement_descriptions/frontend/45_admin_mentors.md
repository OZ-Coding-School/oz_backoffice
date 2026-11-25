# 45. 강사·멘토 > 멘토 (FE-18a)

- 상태: PR 진행 중
- 관련 PR: (작성 후 기록)
- 관련 결정: `docs/decisions.md` F79 (A35·A36·A37·A100~A102)
- 이전 기록: [44. 학사 > 수강생 > 명단 동기화 (FE-17d)](44_academy_roster_sync.md)

## 배경
운영진이 가입한 멘토의 프로필·배정을 보고 대신 고치거나 멘토를 비활성화·활성화한다(F79). 멘토 소개는 길게 마크다운으로 쓰므로 작성·표시 방식도 함께 바꿨다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `components/markdown-editor.tsx` | 공용 마크다운 편집기: '작성 \| 미리보기' 탭 + 큰 입력칸, 미리보기는 공용 `<Markdown>` |
| `features/mentor-profile/profile-editor.ts`, `components/profile-fields.tsx` | 프로필 편집 상태 훅(사진 고르기·줄이기, 폼, 보일 이름)과 입력 부품(사진·이름·닉네임·보일 이름·한 줄 소개·전문 분야 칩·소개)을 멘토 내 프로필에서 떼어 내 운영진 수정과 함께 쓴다. 소개 입력은 마크다운 편집기 |
| `features/mentor-profile/api.ts` | S3 업로드 단계 `postPhoto`를 내보낸다 |
| `features/apply/components/mentor-dialog.tsx`, `team-mentor-step.tsx` | 수강생에게 보이는 멘토 소개를 `<Markdown>`으로 |
| `features/admin-mentors/api.ts` | 목록(20개씩), 단건(A102), 프로필, 배정(A101), 대리 저장(글 먼저·사진 다음), 신청 받기, 비활성화(미리보기·확인), 활성화, 배정 다시 켜기 |
| `features/admin-mentors/components/mentors-page.tsx` | `/admin/educators/mentors?q=&status=`: 상태 선택·검색, 표(이름 · 표시 이름, 연락처(휴대폰 가림), 활성 배정 기수, 계약 수, 신청·상태 배지) |
| `features/admin-mentors/components/mentor-page.tsx` | `/admin/educators/mentors/{id}?tab=assignments`: 머리(이름·활성·신청 배지, 표시 이름·이메일, [비활성화]/[활성화]) + 탭. 배정 탭은 카드를 세로로(기수·배정 중/종료·기간·정산·종료 사유, 비활성은 흐리게) |
| `features/admin-mentors/components/profile-tab.tsx`, `mentor-card-view.tsx` | 프로필 탭: 왼쪽 수강생에게 보이는 모습 + [프로필 수정], 오른쪽 계정·신청 받기. 수정은 같은 자리에서 왼쪽 폼 · 오른쪽 미리보기, 저장 전 떠나면 확인 |
| `features/admin-mentors/components/activation-actions.tsx` | 비활성화: 미리보기로 함께 꺼질 배정·취소될 대기 신청을 보여 주고 확인. 활성화: 확인 후 다시 켤 배정을 고르는 창(기본 모두 선택, 건너뛰기 가능) |
| `features/mentor-schedule/components/accepting-card.tsx` | 신청 받기 카드에 운영진 API(`setter`)와 조회만(`readOnly`)을 넘길 수 있게 |
| `features/staff/nav.ts`, `staff-shell.tsx` | 레일 '강사·멘토' 모듈 › '멘토'(`educator.mentor.read`), 레일 이름 줄바꿈 막기 |
| `routes/_staff/admin/educators/mentors/` | 목록·상세 라우트 |

## 주요 결정 (사용자 결정, F79)
- 표 + 상세 페이지(탭), 프로필 탭은 수강생에게 보이는 모습 중심 2단, 수정은 같은 자리에서 폼 · 미리보기.
- 멘토 소개는 마크다운으로 작성·표시(멘토 내 프로필·수강생 멘토 소개 창 포함).
- 배정은 카드를 세로로 나열(조회만, 추가·수정은 18c).
- 머리의 [비활성화]/[활성화]와 확인 창(A35).
- 계정 칸을 위해 멘토 단건 조회를 백엔드 보완(BE-3u, A102)으로 먼저 더함.
- 수정·스위치·비활성화는 `educator.mentor.manage`가 있을 때만(없으면 버튼을 숨기고 스위치는 막음).

## 발견한 문제와 해결
- 레일 이름 '강사·멘토'가 두 줄로 꺾여 줄바꿈을 막았다.
- 편집기 입력칸의 고정폭 글꼴이 한글 간격을 벌려 기본 글꼴로 바꿨다.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul, 389개), `build`, `e2e`(48개)
- 1440 라이트·다크 화면 확인(목록, 프로필, 수정·미리보기, 배정, 비활성화 확인 창)

## 남은 작업
- FE-18b 계약, FE-18c 기수 배정·일정 대리.
