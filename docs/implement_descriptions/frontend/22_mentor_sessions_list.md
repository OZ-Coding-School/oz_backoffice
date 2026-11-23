# 22. FE-10a 멘토 세션 목록

- 상태: 완료 (2026-11-23 병합)
- 관련 PR: #112
- 관련 결정: `docs/decisions.md` F46·F47·A77
- 이전 기록: [21. FE-9b 멘토 받은 신청 상세·승인·반려](21_mentor_request_detail.md)
- 선행: 백엔드 [76. 멘토 세션 목록 탭·기수 필터 (BE-2k)](../backend/76_mentor_session_views.md)

## 배경
FE-10의 첫 화면 PR이다(F46: BE-2k → 10a 목록 → 10b 상세·기록·메모 → 10c 다시 보기). 멘토가 다가오는 세션과 기록을 내야 하는 세션을 한눈에 보고, 오늘 세션은 바로 Meet에 들어간다.

시안(`Column / 세션`)은 데스크톱만 있었다. 구현 전에 Figma에 그렸다. 위치는 `Member - 멘토 › Column / 세션 · 목록 (FE-10a)`이다.
- 1440: 표
- 768·390: 카드
- 메뉴: 홈·받은 신청·세션·채팅

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `src/routes/_member/mentor/sessions/index.tsx` | `/mentor/sessions?tab=&cohort=`. 멘토만. 목록·배정 기수를 미리 불러온다 |
| `src/features/mentor-sessions/api.ts` | 탭(다가오는 기본·기록 미제출·지난 세션·전체), `view`·이른 순·기수 필터로 20개씩 |
| `src/features/mentor-sessions/labels.ts` | 상태 배지, 기록 칸, Meet 입장 조건, 일시·시간·대상 |
| `components/mentor-sessions-page.tsx` | 머리·탭(view_counts)·기수 필터·표(lg)·카드·빈 상태·이어 불러오기 |
| `src/features/mentor-requests/components/cohort-select.tsx` | 받은 신청과 함께 쓰는 기수 필터 |
| `src/features/member/nav.ts` | 멘토 메뉴 '세션' (배지 없음, F46) |

### 화면 규칙 (F47·A77)
- **탭:** 다가오는(아직 끝나지 않은 예정·진행 중, 이른 순)·기록 미제출(시작했는데 기록 없음)·지난 세션(완료·노쇼·취소)·전체. 건수는 고른 기수 기준이다.
- **상태 배지:**
  - 오늘(오늘 예정), 예정, 진행 중(시작했고 끝나기 전)
  - 진행됨(끝났는데 기록 전), 완료, 노쇼, 취소
- **기록 칸:** 제출했으면 'MM/DD 제출', 시작했는데 기록이 없으면 '미제출', 그 밖은 '—'다.
- **시간:** 신청 시간이고, 완료면 '신청 → 기록' 분이다.
- **동작:** 오늘이거나 진행 중이고, 끝나기 전이고, Meet 링크가 있으면 [Meet 입장]이다. 휴대폰은 카드 아래 전체 폭이다.
- [기록 작성]과 행에서 상세로 가는 링크는 상세 화면과 함께 FE-10b에서 넣는다.

## 주요 결정 (사용자 결정)
- **F46:**
  - PR은 4개로 나눈다(BE-2k·10a·10b·10c). 주소는 `/mentor/sessions`다.
  - 세션 메뉴에 배지는 달지 않는다.
- **A77:** 탭·기수 필터·탭 건수는 백엔드가 계산한다.
- **F47:** 표·카드 시안대로 한다. 상태 배지와 기록 칸 규칙도 시안대로 한다.

## 검증
- `lint`, `format:check`, `typecheck`, `build` 통과
- `npm test`: 225 passed. TZ=UTC·America/Los_Angeles·Asia/Seoul 각각 통과
  - 상태 배지(오늘·예정·진행 중·진행됨·완료), 기록 칸·시간·Meet 입장 조건
  - 기본 다가오는 탭(view·이른 순)·건수·행, 미제출·지난 세션 탭
  - 기수 필터와 건수, 빈 상태
- `npm run e2e`: 27 passed. 데스크톱 메뉴 → 세션 → 오늘 세션 Meet 입장을 추가했다
- 화면 확인: 개발 서버에서 API를 모킹해 1440·768·390 라이트·다크를 확인했다

- GitHub Actions (PR #112): 프론트엔드 검사·E2E 3개 통과
- 사용자가 병합을 확인했다(2026-11-23)

## 남은 작업
- FE-10b 세션 상세·기록 작성·수정·내부 메모
