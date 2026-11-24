# 29. FE-13 멘토 홈

- 상태: 완료 (2026-11-24 병합)
- 관련 PR: #124
- 관련 결정: `docs/decisions.md` F57 (F42·F47·F52·A77)
- 이전 기록: [28. FE-12b 멘토 내 프로필](28_mentor_profile.md)

## 배경
멘토 화면(FE-9~FE-13)의 마지막 PR이다. 지금까지 멘토 홈은 인사말과 빈 상태만 있었다(F27). 멘토가 오늘 처리할 일(대기 신청·오늘 세션·기록 미제출·안 읽은 채팅)과 신청 받기 상태를 한 화면에서 본다.

시안은 데스크톱만 있었다(`Screen / 홈`). 구현 전에 Figma에 그렸다(F49 배치).
- 각 크기 Section: `홈 (FE-13)`. 데스크톱은 기존 시안에 경고 옆 [기록 작성]을 더했고, 처리할 신청의 '마감'을 '가장 이른 희망'으로 바꿨다. 태블릿은 한 열, 휴대폰은 요약 2×2.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/home/mentor-api.ts` | 오늘 세션 수(`from`·`to` KST 하루), 다가오는 세션 3개 + `view_counts`(기록 미제출 수), 가장 오래된 기록 미제출 1개, 대기 신청 3개 + 건수, `desiredSummary` |
| `features/home/components/mentor-home.tsx` | 인사말, 요약 4칸, 기록 미제출 경고, 세션 카드, 처리할 신청 카드, 신청 받기 |
| `features/mentor-schedule/components/accepting-card.tsx` | 일정 화면의 신청 받기 카드를 빼서 홈과 같이 쓴다(설명 문구만 다르게) |
| `features/member/components/member-home.tsx`, `routes/_member/index.tsx` | 멘토 홈 연결, 다가오는 세션·대기 신청·일정 미리 불러오기 |
| `features/auth/test-utils.ts` | 멘토 세션·일정 기본 MSW 응답 |

- 조회 키는 멘토 세션(`["sessions","mentor",…]`)·받은 신청(`["mentor-requests",…]`) 아래에 두어 승인·기록·취소 뒤 함께 다시 부른다.
- 시안의 '마감'은 신청 응답에 없어 '가장 이른 희망 일시'로 바꿨다.

## 주요 결정 (사용자 결정, F57)
- 요약 4칸 + 누르면 이동, 기록 미제출 경고는 있을 때만, 목록 각 3개, 신청 받기 스위치 그대로.

## 검증
- `lint`, `typecheck`, `format:check`, `build` 통과
- `vitest` 283 passed (TZ=UTC·America/Los_Angeles·Asia/Seoul). 새 테스트: 요약·오늘 KST 범위, 경고(하나·여럿·없음), 세션 카드(진행 중·오늘·예정), 처리할 신청(빈 안내 포함), 신청 받기 끄기 확인
- `playwright` 35 passed. 새 E2E: 데스크톱 요약·Meet 입장·경고 → 기록 작성
- 390·768·1440 화면을 시안과 비교했다

- GitHub Actions (PR #124): 프론트엔드 검사·E2E 통과. PR 번호 기록 커밋은 문서만이라 검사를 건너뛰었다(R9 보완 규칙)
- 사용자가 병합을 확인했다(2026-11-24)

## 남은 작업
- 운영진 화면(Figma 다듬기 → BE-3 → FE-14~)
