# 24. FE-10c 멘토 다시 보기 · Figma 크기별 배치

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` F50·F49 (F35·F46·F21)
- 이전 기록: [23. FE-10b 멘토 세션 상세·기록·내부 메모](23_mentor_session_detail.md)

## 배경
FE-10의 마지막 PR이다(F46). 멘토가 완료 세션의 녹화·전사본·스마트 메모를 다시 본다. 수강생 다시 보기(FE-5b)를 그대로 쓴다.

이 PR을 시작하기 전에 사용자 요청으로 Figma를 정리했다. 화면 페이지(Login·Member·Admin)를 크기별 Section으로 나눠 가로로 놓았다. 순서는 데스크톱 1440 → 태블릿 768 → 모바일 390 → 상태·모달 → 초기 시안이다. 앞으로도 이 규칙을 따른다(F49, 작업 하네스 3-2).

구현 전에 Figma에 그렸다. 위치는 `Member - 멘토`의 각 크기 Section 안 `세션 · 다시 보기 (FE-10c)` 묶음이다(1440·768·390).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `src/features/mentor-sessions/components/mentor-session-page.tsx` | 완료 세션이면 머리 아래 전체 폭에 `ReplaySection`(FE-5b) |
| `src/features/mentor-sessions/detail.test.tsx` | 완료 세션 다시 보기·순서, 기록 전 세션은 없음 |
| `apps/frontend/CLAUDE.md` | 작업 하네스 3-2 Figma 배치 규칙 |

### Figma 정리 (F49)
- 페이지마다 크기별 Section을 가로로 놓는다. Section 안에는 기능 순서대로 `Group / <기능>` 묶음과 라벨을 둔다. 기능 설명은 첫 묶음에 둔다.
- 화면 이름의 크기(태블릿·모바일·데스크톱)나 폭(768·390·1440)으로 나눴다. 그 밖은 상태·모달 Section이다.
- 태블릿·모바일 묶음은 줄바꿈 격자로 놓는다.
- FE 화면으로 다시 그린 예전 시안 열은 `초기 시안` Section으로 옮겼다. 수강생 9개, 멘토 4개다.
- Admin 9개 페이지는 데스크톱 Section에 화면을 옮겼다. 비어 있는 태블릿·모바일 Section에는 구현 전에 그린다는 안내를 넣었다. Admin - 공통은 부품 페이지라 그대로 두었다.

## 주요 결정 (사용자 결정)
- **F50:** 다시 보기는 완료 세션만, 머리 아래 전체 폭에 둔다.
- **F49:** Figma 화면 페이지는 크기별 Section을 가로로 놓고, 앞으로의 모든 화면 작업에 적용한다.

## 검증
- `lint`, `format:check`, `typecheck`, `build` 통과
- `npm test`: 236 passed. TZ=UTC·America/Los_Angeles·Asia/Seoul 각각 통과
  - 완료 세션의 다시 보기(내려받기)가 기록 카드보다 앞에 온다
  - 기록 전 세션은 다시 보기가 없다
- `npm run e2e`: 28 passed
- 화면 확인: 개발 서버에서 API를 모킹해 1440·768·390 라이트·다크를 확인했다

## 남은 작업
- 실제 Meet 녹화로 멘토 다시 보기 확인
- FE-11 멘토 일정
