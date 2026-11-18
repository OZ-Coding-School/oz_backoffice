# 62. 수강생 멘토링 신청 준비 API (BE-1)

- 상태: 완료 (2026-11-18 병합)
- 관련 PR: #81
- 관련 결정: `docs/decisions.md` A64, F12·F13 (프론트엔드 계획 BE-1)
- 이전 기록: [61. 조교 담당 기수는 비어 있는 기수만](61_cohort_assistant_filter.md)

## 배경
FE-2(회원 공통 틀)와 FE-3(수강생 멘토링 신청)에 필요한 수강생용 조회 API가 없었다.
- 상단 기수 선택에 쓸 내 수강 등록
- 신청 단계를 정할 기수 멘토링 설정
- 1:1 멘토 선택에 쓸 멘토 공개 프로필

기수 설정과 멘토 정보는 운영진용 API만 있었다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `academy/application/enrollment_queries.py` | `EnrollmentQueries.of_user`: 내 수강 등록 + 기수·과정, 기수 시작일이 늦은 것부터 |
| `academy/presentation/me_router.py` | `GET /me/enrollments` |
| `mentoring/application/student_queries.py` | `StudentMentoringQueries`: 설정 요약, 신청 받는 멘토, 멘토 한 명. 모두 그 기수의 수강 중 수강생만 |
| `mentoring/presentation/student_router.py` | `GET /me/mentoring/settings`, `/mentors`, `/mentors/{id}` (모두 `cohort_id` 필수) |
| `api/v1.py` | 라우터 등록 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

### API

| API | 내용 |
| --- | --- |
| `GET /me/enrollments` | 내 수강 등록 전부(상태 무관). 과정 이름·기수 번호·기수 기간·기수 상태·수강 상태·등록일·종료일. 없으면 빈 목록 |
| `GET /me/mentoring/settings?cohort_id=` | 허용 종류(1:1·팀), 진행 단위, 신청 마감 시간, 대기 신청 최대 건수. 설정이 없으면 404 `mentoring_settings_not_configured` |
| `GET /me/mentoring/mentors?cohort_id=` | 그 기수에 활성 배정된 활성 멘토 중 신청 받기를 켠 멘토. 표시 이름·한 줄 소개·전문 분야·사진(presigned 10분). 표시 이름순 |
| `GET /me/mentoring/mentors/{id}?cohort_id=` | 배정된 멘토면 신청을 받지 않아도 보인다. 목록 항목 + 소개·신청 받기 여부. 배정이 없으면 404 `mentor_not_assigned` |

- 수강 중이 아니면 설정·멘토 API는 403 `not_enrolled_in_cohort`를 돌려준다.
- 공개 프로필에는 실명·연락처를 따로 넣지 않는다. 표시 이름은 멘토가 고른 대로 실명 또는 닉네임이다.
- 회원 한 명의 수강 등록과 기수 멘토 수는 적어 페이지를 나누지 않았다(팀 목록 API와 같음).

## 주요 결정 (사용자 결정, A64)
- 수강 등록은 상태와 무관하게 모두 보낸다(지난 기수 기록도 볼 수 있게).
- 설정 요약은 신청 화면에 필요한 네 값만 보낸다. 운영시간·금지 시간대·휴일은 신청 가능 시간 API가 이미 반영한다.
- 멘토는 목록(신청 받는 멘토만) + 단건(배정된 멘토면 보임)으로 둔다.
- PR 하나로 만든다.

## 검증
- API (실제 DB)
  - 내 수강 등록: 상태 무관 전부, 다른 사람 제외, 등록 없음(빈 목록), 401
  - 설정·멘토
    - 설정 없음 404와 네 값
    - 목록은 신청 받는 멘토만(닉네임 표시, 소개 없음, 실명 없음)
    - 단건은 신청을 받지 않는 배정 멘토도 보이고, 다른 기수 멘토·없는 멘토는 404
    - 수강생이 아니면 403, 비로그인 401
- 통합: 수강 등록 정렬(기수 시작일이 늦은 것부터)
- 로컬 검사 (compose `api`): ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 867 passed.
- 프론트엔드: 다시 만든 타입으로 `typecheck` 통과
- GitHub Actions (PR #81): 백엔드 검사·프론트엔드 검사(타입 일치 포함)·E2E 통과
- 사용자가 병합을 확인했다(2026-11-18)

## 남은 작업
- FE-2 회원 공통 틀(기수 선택), FE-3 신청 화면에서 사용
