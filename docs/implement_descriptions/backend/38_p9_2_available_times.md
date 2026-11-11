# 38. P9-2 신청 가능 시간 계산·조회

- 상태: PR 진행 중
- 관련 PR: #43
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P9 (P9-2)
- 이전 기록: [37. P9-1 멘토 불가 시간·신청 받기·기수 운영시간](37_p9_1_mentor_schedule.md)

## 배경
P9의 두 번째 PR이다. P9-1에서 만든 재료(멘토 불가 시간, 신청 받기, 기수 운영시간)와 P8의 금지 시간대·배정으로 멘토의 신청 가능 시간을 계산해 보여 준다. 수강생은 이 구간 안에서 희망 일시를 고르고(P11), 신청 검증도 같은 계산을 쓴다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/availability.py` | 순수 계산 `available_intervals`. 구간 빼기(`subtract`), 배정 기간(`AssignmentRange`) |
| `mentoring/application/availability_service.py` | `AvailableTimesService`: 조회 권한, 기간 검증, 설정·배정 확인, 재료 조회 후 계산. 세션은 `BusySchedule` 포트(P9는 `NoBusySchedule`) |
| `academy/application/student_queries.py` | `StudentQueries.is_enrolled`(그 기수 명단에 연결되고 수강 중인지, `app.state.student_queries`) |
| `mentoring/presentation/availability_router.py` | `GET /api/v1/mentors/{id}/available-times?cohort_id=&from=&to=` |

**계산 순서 (한국 날짜 기준):**
1. 날짜마다 그 기수의 활성 배정 기간(유형 무관 합집합) 안인지 본다.
2. 영업일(평일·비공휴일)이면 평일 운영시간, 아니면 주말·공휴일 운영시간으로 연다. 운영 안 함이면 닫는다.
3. 금지 시간대(그 기수, 영업일에만)를 뺀다.
4. 멘토 불가 시간을 뺀다. 반복 회차는 전개하고, 자정을 넘는 회차를 위해 하루 앞부터 본다.
5. 이미 잡힌 세션을 뺀다(P11부터).
6. 신청 마감(지금 + `min_lead_hours`, 30분 경계로 올림) 전 시각을 뺀다.
7. 이어지는 구간을 합친다(자정을 넘어도). 진행 단위보다 짧은 구간은 버린다.

**응답:** `accepting_requests`, `allowed_duration`, `min_lead_hours`, `intervals[{starts_at, ends_at}]`(UTC, 시작 순)

## 주요 결정 (A37, P9 시작 전에 확정)
- 볼 수 있는 사람: 그 기수의 수강 중(ENROLLED) 수강생, 운영진(`mentoring.request.read` 기수 범위), 멘토 본인
- 멘토가 그 기수에 활성 배정(유형 무관)돼 있어야 하고, 배정 기간 안의 날짜만 연다.
- 응답은 연속 가능 구간 목록이다. 진행 단위보다 짧은 구간은 버린다.
- 기수 설정이 없으면 404 `mentoring_settings_not_configured`다.
- 조회는 한 번에 최대 31일, 오늘부터 60일 뒤까지다.

## 결정에서 정하지 않아 구현에서 정한 것 (확인 요청)
- `from`이 오늘보다 앞이거나 범위를 벗어나면 잘라서 주지 않고 422 `invalid_time_range`로 거부한다.
- 그 기수에 활성 배정이 없으면 404 `mentor_not_assigned`다.
- 신청 받기가 꺼져 있거나 멘토가 비활성이면, 오류 대신 `accepting_requests=false`와 빈 목록을 준다(프론트가 안내 문구를 띄울 수 있게).
- 권한이 없는 회원은 403이다. 운영진 판정은 `mentoring.request.read`를 그 기수 범위로 검사한다.

## 검증
- 단위:
  - 계산: 평일·주말·공휴일 운영시간, 운영 안 함, 자정을 넘어 이어지는 운영시간, 일회성·매일·매주 불가 시간, 전날 밤부터 이어지는 불가 시간, 금지 시간대(주말 미적용), 세션, 신청 마감(30분 올림), 진행 단위 미만 버림, 배정 기간, 구간 빼기 경계(맞닿음·전체·길이 0)
  - 서비스: 수강생·멘토·운영진·그 외(403), 기간 위반 4종과 경계(31일·60일 뒤), 미배정 404, 설정 없음 404, 신청 받기 꺼짐
- API(실제 DB):
  - 설정 없음 404 → 신청 받기 꺼짐(빈 목록) → 켜고 매일 점심 불가 등록
  - 7일 × 두 구간(10~12시, 13~19시)
  - 멘토 본인·운영진 200, 다른 회원 403, 비로그인 401, 32일 422
- 전체 646 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 코드 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(637 → 645 → 646 passed)

## 남은 작업
- P11: `BusySchedule`(잡힌 세션)·`ScheduleConflictFinder`(불가 시간 충돌) 구현, 신청 시 희망 일시가 가능 구간 안인지 같은 계산으로 검증
- 성능: 조회마다 멘토 불가 시간 전체와 그 기수 금지 시간대를 읽는다. 지금 규모(멘토당 수십 건)에서는 충분하다. 늘어나면 기간으로 거른다
