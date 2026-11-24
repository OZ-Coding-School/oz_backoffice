# 80. CI 시간 줄이기

- 상태: 완료 (2026-11-24 병합)
- 관련 PR: #121
- 관련 결정: `docs/decisions.md` R9 (R5·F19)
- 이전 기록: [79. 정산 응답에 기수·항목 상대·주제 (BE-2n)](79_settlement_labels.md)

## 배경
사용자가 CI가 너무 오래 걸린다고 분석과 해결을 요청했다. 최근 30개 실행을 보면 평소에는 1.5~3.5분이었다. 그런데 5~11분 걸린 실행이 자주 있었다.

| 원인 | 근거 |
| --- | --- |
| E2E 작업의 `npx playwright install-deps`(apt)가 가끔 매우 느림 | 보통 10초, 느린 실행 7개 중 6개에서 207~353초 |
| E2E 샤드 3개 | 테스트는 샤드당 7~19초인데 npm ci·apt·빌드를 3번 한다. 느린 apt를 만날 확률도 3배 |
| 취소된 실행이 apt에 걸려 늦게 끝남 | #120에서 새 실행이 5분 기다렸다 (같은 concurrency 그룹) |
| 문서만 바꾼 커밋도 전체 검사 | PR마다 생성·PR 번호 기록·완료 처리로 3번 실행. `paths-filter`는 PR 전체 변경을 본다 |
| 정상일 때 긴 단계 | vitest 66~89초, pytest 69~114초, mypy 29~41초(캐시 없음) |

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `.github/workflows/ci.yml` | 변경 감지를 `git diff`로 바꿨다(이어 올린 커밋은 이전 head와, 처음 열거나 rebase면 PR 전체와, main·develop push는 이전 커밋과 비교). 백엔드 mypy 캐시. E2E는 Playwright 컨테이너(`v1.65.1-noble`, `--user 1001`) 작업 하나, 버전 일치 확인. 이제 필요 없는 `frontend_ready` 검사를 뺐다 |
| `apps/frontend/playwright.config.ts` | CI 워커 `"100%"` |
| `apps/frontend/CLAUDE.md` | E2E 실행 방식과 Playwright 버전을 올릴 때 할 일 |

- vitest는 4코어 조건(`--maxWorkers=3·4`, `forks`·`threads`)에서 모두 28~30초라 설정을 바꾸지 않았다. 격리 끄기(`isolate: false`)는 테스트 상태가 섞일 수 있어 하지 않았다.

## 주요 결정 (사용자 결정, R9)
- Playwright 공식 컨테이너, 샤드 합치기, 마지막 push의 변경만 보기, mypy 캐시, vitest 측정 후 판단.

## 검증
- actionlint: 새 경고 없음 (기존 S3 대기 스크립트의 SC2034 하나)
- 프론트엔드 `typecheck`, `format:check` 통과
- GitHub Actions (PR #121): 전체 검사 통과. Playwright 컨테이너 E2E 작업 74초(전: 샤드 3개 각 40초~6분). 문서만 바꾼 커밋은 검사를 건너뛰어 9초
- 사용자가 병합을 확인했다(2026-11-24)

## 남은 작업
- 몇 번의 PR에서 실행 시간을 다시 확인한다.
