# 35. P8-1 기수 멘토링 설정·금지 시간대·추가 휴일

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P8 (P8-1)
- 이전 기록: [34. P7-5 수강생·멘토 가입 승인 관리와 재신청](34_p7_5_signup_approvals.md)

## 배경
P8의 첫 PR이다. 기수마다 멘토링 규칙(허용 방식, 기본 지급 시간, 신청 마감, 진행 단위, 대기 신청 수)과 멘토링 금지 시간대를 관리한다. 금지 시간대는 평일에만 적용해야 해서, 한국 공휴일과 운영진이 등록하는 추가 휴일을 판단하는 영업일 계산도 함께 만든다. 금지 시간대를 실제로 적용하는 곳은 멘토 일정 열기(P9)와 신청(P11)이다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/settings.py` | `CohortMentoringSettings`(값 제한), `MentoringBlockTime`(기간·시각 검증, 겹침, 평일 적용), `MentoringHoliday` |
| `mentoring/infrastructure/models/settings.py`, `migrations/models/11_…` | `cohort_mentoring_settings`, `cohort_mentoring_block_times`, `mentoring_holidays` + raw SQL(기본값, check, 겹침 EXCLUDE) |
| `mentoring/infrastructure/repositories.py` | 리포지토리. 금지 시각은 시간대 없는 `TIME`으로 저장·조회한다 |
| `mentoring/application/calendar.py` | `BusinessCalendar`: 평일 − 법정공휴일(`holidays`) − 추가 휴일 = 영업일 |
| `mentoring/application/settings_service.py` | 설정 첫 저장·조회, 금지 시간대 CRUD(겹침 409), 추가 휴일 등록·삭제, 감사 로그 |
| `mentoring/presentation/settings_router.py` | API (아래 표) |

| 메서드 | 경로 | 권한(`mentoring.settings.manage`) |
| --- | --- | --- |
| GET / PUT | `/api/v1/admin/cohorts/{cohort_id}/mentoring-settings` | 기수 범위. 없으면 GET 404 `mentoring_settings_not_configured` |
| GET / POST | `/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times` | 기수 범위 |
| PATCH / DELETE | `/api/v1/admin/cohorts/{cohort_id}/mentoring-block-times/{id}` | 기수 범위 |
| GET | `/api/v1/admin/mentoring-holidays?year=` | 담당 범위가 있으면. 법정공휴일(PUBLIC) + 추가 휴일(CUSTOM) |
| POST / DELETE | `/api/v1/admin/mentoring-holidays[/{id}]` | 담당 범위가 있으면 |

## 주요 결정 (사용자 결정, A34·B15)
- **PR 분할:** P8-1(설정·금지 시간대)과 P8-2(멘토 배정)로 나눈다.
- **설정 생성:** 첫 저장 때 만든다. 없는 기수를 조회하면 기본값 대신 "설정 필요" 오류를 주고, 프론트가 설정 페이지로 안내한다.
- **설정 값 제한:** 진행 단위 30·60분, 신청 마감 6·12·24시간, 대기 신청 1~3건, 기본 지급 시간 60분 단위, 팀·1:1 중 하나 이상. 신청 마감(`min_lead_hours`)의 의미를 설명한 뒤 선택지로 정했다.
- **금지 시간대 적용 대상:** 신청과 멘토 일정 열기를 모두 막는다. 일정 열기는 멘토가 그 기수에만 배정돼 있을 때만 막고, 여러 기수에 배정된 멘토는 신청만 막는다.
- **금지 시간대 적용일:** 평일(월~금)에만 적용하고 주말·공휴일·연휴에는 적용하지 않는다.
- **겹침과 수정:** 같은 기수에서 기간과 시간대가 모두 겹치면 거부한다. 기간 제한은 없고, 언제든 수정·삭제하며 소급하지 않는다.
- **공휴일 판단:**
  - 사용자가 처음 고른 `holidayskr`의 소스를 확인했다. import 때 GitHub 원격 JSON을 받아오고(타임아웃 없음, 실패 시 50회 재시도), 2024-02 이후 관리되지 않는다. 이를 보고한 뒤 `holidays` 패키지(오프라인 계산)로 바꿨다.
  - 추가 휴일은 전사 공통이고, 담당 범위가 있는 매니저도 관리한다.

## 발견한 문제와 해결
- Tortoise(use_tz)의 `TimeField`가 `TIMETZ` 컬럼을 만들었다. 금지 시각은 한국 시각의 "시:분"이라 마이그레이션에서 `TIME`으로 바꿨다. 조회 때 붙는 UTC 표시는 떼고, 저장 때 생기는 시간대 없는 시각 경고는 표시만 붙여 없앴다(통합 테스트로 시각 유지 확인).
- 겹침 금지는 서비스 검사(409 `block_time_overlap`)와 DB EXCLUDE(`daterange` × `tsrange`)를 함께 건다. 시간대가 맞닿기만 하는 경우(09–12, 12–18)는 허용한다.

## 검증
- 단위: 설정 값 제한 9가지와 변경 항목 제한, 금지 시간대 검증·겹침·평일 적용, 휴일 이름, 공휴일(2026 추석 연휴·개천절·한글날), 영업일(추가 휴일·주말·공휴일 제외)
- 통합(PostgreSQL): 설정 왕복·기수당 하나·DB check 5종, 금지 시각 왕복(시간대 없음), EXCLUDE(겹침 거부·맞닿음·다른 기간·다른 기수 허용), 추가 휴일 유일·기본값
- API:
  - 설정: 없을 때 404 → 저장 → 수정, 규칙 위반 422(방식 없음·60분 단위·목록 밖 값)
  - 금지 시간대: CRUD, 겹침 409(생성·수정), 다른 기수 경로 404
  - 휴일: 조회(PUBLIC·CUSTOM), 중복 409
  - 권한: 매니저 담당 기수 200·다른 기수 403, 조교 403, 매니저 추가 휴일 등록, 비로그인 401
- 커밋 4개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 566 passed다.

## 남은 작업
- P8-2 멘토 배정(계약 기간 검증, 겹침 EXCLUDE, MENTOR 역할, 본인 배정 조회)
- 금지 시간대·영업일 적용: P9(일정 열기), P11(신청)
