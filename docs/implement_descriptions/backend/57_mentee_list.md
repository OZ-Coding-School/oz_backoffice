# 57. 운영진 멘티 목록·신청·세션 수 집계

- 상태: 완료 (2026-11-16 병합)
- 관련 PR: #64
- 관련 결정: `docs/decisions.md` A59
- 이전 기록: [56. 운영진 신청·세션·채팅방 목록 필터](56_admin_list_filters.md)

## 배경
Figma에서 운영진 멘토링 메뉴에 멘티 관리를 두기로 했다(F3). 이 화면은 기수 수강생을 멘토링 관점(계좌 잔여, 팀, 신청·세션 수)으로 보여 주는데, 여기에 맞는 API가 없었다. 기존 계좌 목록은 계좌가 있는 수강생만 나오고 신청·세션 수도 없다. A59의 두 번째 PR이다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `academy/application/student_queries.py` | `in_cohort(cohort_id, statuses, name)`: 기수 명단을 수강 상태와 이름(부분 일치)으로 거른다. 원천에서 삭제된 등록은 빼고 이름순으로 돌려준다. |
| `mentoring/domain/repositories.py`, `infrastructure/repositories.py` | 신청: `count_pending_by_requesters`(수강 등록별 1:1 대기 신청 수). 세션: `count_by_requesters`(수강 등록별 1:1 세션 수, 상태별). 둘 다 GROUP BY 한 번이다. |
| `mentoring/application/mentee_queries.py` | `MenteeQueries.list`: 명단을 페이지로 자른 뒤, 그 페이지 수강생의 팀·계좌·건수만 묶어 읽는다. |
| `mentoring/presentation/mentee_router.py` | `GET /api/v1/admin/cohorts/{cohort_id}/mentoring/mentees` |
| `api/v1.py` | 라우터 등록 |

**`GET /admin/cohorts/{cohort_id}/mentoring/mentees`**

- 권한: `mentoring.request.read`(기수 범위)
- 쿼리 파라미터
  - `status`: 수강 상태. 여러 번 줄 수 있고, 비우면 명단 전체다.
  - `q`: 이름 부분 일치
  - `limit`: 기본 50, 최대 100
  - `offset`
- 정렬: 이름순
- 항목
  - 수강 정보: `student_id`, `name`, `is_signed_up`, `status`
  - `team`: `id`, `label`
  - `account`: 1:1 계좌. 기간, 만료 여부, 총·보류·사용·잔여 분. 지급 전이면 null이다.
  - 건수: `pending_request_count`, `upcoming_session_count`, `completed_session_count`

## 주요 결정 (사용자 결정, A59)
- **멘티 목록 API를 새로 만든다.** 계좌 목록 확장이 아니어서 계좌가 없는 수강생도 나온다.
- **대상은 명단 전체이고 수강 상태로 거른다.** 원천(Airtable)에서 삭제된 등록은 학사 명단과 같이 뺀다.
- **검색은 이름만 둔다.** 정렬은 이름순으로 고정한다.
- 권한은 신청·세션 목록과 같은 **`mentoring.request.read`**다. 시간 지급 버튼은 화면이 `mentoring.balance.grant`로 따로 판단한다.
- **건수는 1:1 기준이다.**
  - 대기 신청: PENDING
  - 예정 세션: SCHEDULED, IN_PROGRESS
  - 완료 세션: COMPLETED
  - 취소·반려·노쇼는 세지 않는다. 팀 건은 팀 관리에서 본다.

## 구현 세부
- **스키마 변경 없음.**
- **조회 쿼리는 요청마다 6개로 고정된다**(권한 검사 제외).
  - 명단 1개
  - 팀 소속 1개, 팀 1개
  - 계좌 1개
  - 대기 신청 수 1개, 세션 수 1개
- **명단은 기수 단위로 한 번에 읽고 서버 메모리에서 거른다.** 기수 명단은 수백 명 규모이고, 기존 `enrolled_in_cohort`도 같은 방식이다. 계좌·건수는 잘라 낸 페이지의 수강생만 읽는다.
- **인덱스:** 건수 집계는 신청의 `(requester_id, created_at)` 인덱스를 쓰고, 세션은 신청과 1:1 조인한다.

## 검증
- **단위 테스트**(인메모리)
  - 팀·계좌·건수 조합 확인. 팀 신청·세션, 취소 세션은 세지 않는다.
  - 상태·이름 필터, 페이지네이션, 범위 밖 offset.
- **통합 테스트**
  - 수강 등록별 대기 신청 수(팀 신청 제외, 빈 목록).
  - 세션 수(팀 세션 제외, 빈 목록).
- **API 테스트**
  - 계좌·팀이 응답에 들어간다. 중도포기 수강생은 계좌 없이 나오고, 원천에서 삭제된 등록은 빠진다.
  - 상태 필터(하나, 여럿), 이름 검색, 페이지네이션.
  - 수강생 403, 비로그인 401.
- **로컬 검사 (compose `api` 컨테이너):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 830 passed.
- GitHub Actions (PR #64) backend 잡 통과 후 병합
- 사용자가 병합까지 진행하도록 승인했다(2026-11-16)

## 남은 작업
- 프론트엔드 멘티 관리 화면에서 이 API를 쓴다.
