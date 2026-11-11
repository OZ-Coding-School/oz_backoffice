# 37. P9-1 멘토 불가 시간·신청 받기·기수 운영시간

- 상태: 완료 (2026-11-11 병합)
- 관련 PR: #42
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P9 (P9-1)
- 이전 기록: [36. P8-2 기수 멘토 배정·멘토 활성화·팀리드 권한](36_p8_2_cohort_mentors.md)

## 배경
P9의 첫 PR이다. 멘토 일정 등록을 만들고, 신청 가능 시간 계산(P9-2)의 재료를 준비한다. 재료는 멘토 불가 시간, 신청 받기 여부, 기수 운영시간이다.

처음에는 계획대로 구현해 PR을 열었다. 멘토가 요일별 가능 시간을 등록하고 예외 불가 일정으로 일부를 닫는 방식이었다. 리뷰 중 사용자가 "불가능한 시간만 등록하면 나머지는 가능으로 보면 되지 않나"라고 물었다. 두 방식의 장단점을 비교한 뒤, 사용자가 불가 시간 중심으로 바꾸기로 했다(M1 변경). 같은 PR에서 다시 구현했다. 마이그레이션 13은 develop에 병합된 적이 없어 새 설계로 교체했다(사용자 결정).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/schedule.py` | `MentorUnavailablePeriod`: 일회성·매일·매주, 기준 회차 + 반복 종료일, 30분 경계, UTC 정규화, 회차 24시간 이하, 분류·메모, 시작 여부, 끝남 판정, 회차 전개(`occurrences`) |
| `mentoring/domain/settings.py` | `OperatingHours`(자정부터 지난 분 0~1440, 30분 경계). 설정에 평일, 주말·공휴일 운영시간(기본 평일 10:00~19:00, 주말 운영 안 함) |
| `educator/domain/profiles.py`, `application/mentor_queries.py` | `Mentor.accepting_requests`와 `set_accepting`. 비활성 멘토는 켤 수 없고, 비활성화하면 꺼진다 |
| `migrations/models/13_…` | `mentor_unavailable_periods` 생성, `mentors.accepting_requests`·설정 운영시간 컬럼 추가, check 7종 |
| `mentoring/application/schedule_service.py` | `MentorScheduleService`: 일정 조회, 신청 받기, 불가 시간 등록·전체 교체·삭제, 충돌 미리보기(`ScheduleConflictFinder` 포트), 감사 로그 |
| `mentoring/presentation/schedule_router.py`, `settings_router.py` | API (아래 표), 설정 PUT·GET에 `weekday_hours`·`weekend_hours` |

| 메서드 | 경로 (멘토 본인 `/api/v1/me/mentor-schedule`, 운영진 대리 `/api/v1/admin/mentors/{id}/schedule`) | 비고 |
| --- | --- | --- |
| GET | `…?include_past=` | 신청 받기 + 불가 시간(기본은 끝나지 않은 것) |
| PUT | `…/accepting` | 신청 받기 켜기·끄기 |
| POST | `…/unavailable-periods?confirm=` | 저장 201 / 충돌 미리보기 200(`applied=false`) |
| PUT / DELETE | `…/unavailable-periods/{id}` | 전체 교체(`?confirm=`) / 204 |

불가 시간 입력은 세 가지다.
- 일회성: 시각(`starts_at~ends_at`) 또는 종일(`all_day`, `start_date~end_date`)
- 매일·매주: 기준 회차 `starts_at~ends_at`
- 매주는 `weekdays`(1=월~7=일)를 받고, 반복 종료일 `repeat_until`은 선택이다.

## 주요 결정 (사용자 결정, A37)
- **불가 시간 중심:** 멘토는 불가 시간만 등록한다. 요일별 가능 시간 테이블(`mentor_availabilities`)은 두지 않는다.
- **유형:** 일회성 / 반복이다.
  - 반복 규칙은 매일, 매주(요일 여러 개) 두 가지다. 중간에 "주별·월별"과 "매주·매일"로 답이 엇갈려 다시 확인했다.
  - 분류는 자유 입력이다.
- **입력 방식:**
  - 처음에는 반복 시각을 하루 중 분으로 저장하려 했다. 사용자가 "시작·종료를 날짜시각으로 받으면 자정 넘김 문제가 없어지지 않나"라고 물었다.
  - 그래서 캘린더처럼 기준 회차의 날짜시각 + 반복 규칙으로 받고, 일회성과 한 테이블에 둔다.
  - 자정을 넘겨도 되고, 반복 회차는 24시간 이하다.
- **변경 규칙:** 일회성은 시작 전까지만, 반복은 언제든 수정·삭제한다. 불가 시간끼리는 겹쳐도 된다. 적용 기간(반복 종료일)은 선택이다.
- **열린 시간:**
  - 멘토 쪽은 24시간 열려 있지만, 수강생은 기수 운영시간 안에서만 고른다.
  - 운영시간은 평일, 주말·공휴일로 나누고 각각 시작~끝 또는 운영 안 함이다.
  - 기본값은 평일 10:00~19:00, 주말·공휴일 운영 안 함이다.
- **신청 받기:** 멘토 단위 스위치로 기본은 꺼짐이다. 멘토 본인·운영진이 바꾸고, 끄면 새 신청만 막는다.
- **충돌 처리:**
  - 불가 시간이 늘어나는 변경이 대기 신청·승인 세션과 충돌하면 미리보기 → confirm 시 저장한다. 충돌 신청은 반려, 세션은 취소(환불)하고 알린다.
  - P9는 미리보기 틀만 둔다. 실제 처리는 P11, 알림은 M24 결정 때 붙인다. (재설계 전과 같음)
- **이전 설계에서 사라진 결정:**
  - 가능 시간 겹침 409, 공휴일 적용, 그 기수에만 배정된 멘토에게 주던 금지 시간대 경고는 없어졌다(가능 시간을 "여는" 동작이 없으므로).
  - 금지 시간대는 계산에서 뺀다(A34).

## 구현 세부
- **회차 전개(`occurrences`):** 반복 규칙을 조회 구간 안의 회차 목록으로 펼친다(P9-2 계산과 P11 충돌 검사가 쓴다).
  - 자정을 넘는 회차를 놓치지 않도록 구간 하루 앞부터 본다.
  - 매주 반복은 기준 회차 날짜부터 고른 요일마다 생긴다. 기준 날짜가 고른 요일이 아니면 첫 해당 요일부터 시작한다.
- **저장 형식:**
  - 매주 요일은 비트(월=1 … 일=64) `weekdays_mask`로 저장한다.
  - 운영시간은 24:00을 표현하려고 자정부터 지난 분(smallint)으로 저장한다. API는 `"HH:MM"`(`"24:00"` 가능)이다.
- **기본값 반영:** 이미 저장된 기수 설정에는 마이그레이션 기본값(평일 600~1140분, 주말 NULL)이 들어간다.
- **감사 로그:**
  - 불가 시간: `mentoring.unavailable_period.create|update|delete`
  - 신청 받기: `educator.mentor.accepting_requests`(값이 바뀔 때만)

## 발견한 문제와 해결
- **운영시간 check:** 시작만 있고 끝이 NULL인 경우를 통과시켰다. `open < close`가 NULL로 평가되면 CHECK는 통과하기 때문이다. 두 값의 NOT NULL을 명시하도록 고쳤고, 통합 테스트로 확인했다.
- **`aerich downgrade -v N`:** 이 명령은 "N 이전으로" 되돌린다. 버전 N 자체를 지운다.
  - 마이그레이션 13을 되돌리려고 `-v 12`를 실행하자 12(`cohort_mentors`)까지 내려가, **개발 DB의 `cohort_mentors` 테이블이 삭제**됐다. 그 안에 있던 배정 데이터가 있었다면 사라졌다. 이후 12를 다시 적용했다.
  - 13만 되돌리려면 `-v 13`을 쓴다.
- **응답 시간대:** 예외 일정 응답이 입력 시간대(+09:00)와 DB 읽기(UTC)로 달랐다. 엔티티에서 UTC로 정규화했다(재설계 전 발견).
- **`btree_gist`:** EXCLUDE에 필요한 `btree_gist` 확장은 로컬 init SQL에서만 만든다. 이 PR은 EXCLUDE를 새로 쓰지 않지만, 운영 DB에서 먼저 만들어야 한다는 내용을 운영 참고 문서(PR #41)에 추가했다.

## 검증
- 단위:
  - 도메인: 규칙 위반 12종, UTC 정규화, 종일 변환, 시작 여부, 끝남 판정, 회차 전개(일회성·맞닿음, 매일 자정 넘김·반복 종료일·기준 회차 전, 매주 월말 넘김), 요일 비트, 운영시간(24:00·경계·형식), 신청 받기 스위치
  - 서비스: 일회성·반복 등록(지난 반복 허용·겹침 허용·지난 일회성 거부), 비활성·없는 멘토, 교체·삭제 규칙, 충돌 미리보기→confirm(저장 안 함·변경 후 전체 전달), 신청 받기·조회 필터
- 통합(PostgreSQL): 매주 반복 왕복(요일·분류·종료일), 겹침 허용, check 8종, 운영시간 왕복(24:00·운영 안 함)과 check 4종, 신청 받기 저장
- API:
  - 불가 시간: 매주·매일(자정 넘김)·종일 등록, 잘못된 입력 422 4종, 교체, 조회, 삭제
  - 신청 받기: 켜기 → 멘토 비활성화 시 꺼짐 → 켜기·등록 거부
  - 운영진 대리, 권한(조교 403, 비로그인 401, 프로필 없음 404)
  - 기수 운영시간: 기본값, 사용자 지정, 24:00, 잘못된 값
- 전체 629 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- GitHub Actions (PR #42): backend 잡 통과, 629 passed
- 사용자가 작업 완료를 확인했다(2026-11-11)
- 마이그레이션: upgrade → migrate("No changes detected") → downgrade -v 13 → upgrade. DBML `@dbml/core` 11 검증(43개 테이블)
- 코드 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(619 → 625 → 629 passed)

## 남은 작업
- P9-2 신청 가능 시간 계산·조회 API (운영시간 − 불가 시간 − 금지 시간대 − 세션 − 신청 마감)
- P11: 충돌 검사 구현(`ScheduleConflictFinder`)과 충돌 신청 반려·세션 취소, 알림(M24)
