# 98. 수강생 상세 API (BE-3r)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #156
- 관련 결정: `docs/decisions.md` A99 (F73·F76, A59)
- 이전 기록: [97. HRD 연결 정보 (BE-3q)](97_hrd_links.md)

## 배경
FE-17c 학사 > 수강생 상세 페이지(탭: 기본 정보·멘토링, F76)에 필요한 값을 한 번에 주는 API다. 처음 만든 기수 명단 상세 + 다른 기수 이력 API(#155)는 화면 설계를 바꾸면서 닫고 새로 설계했다(A99).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `academy/application/student_detail.py` | 상세 값(`StudentDetail`: 수강생·가입 계정·멘토링 요약)과 `StudentDetailReader` 포트 |
| `app/composition/student_detail.py` | `StudentDetailComposer`: 명단에서 수강생(그 기수가 아니면 404 `student_not_found`), 회원에서 가입 계정(이메일·승인일), 멘토링 요약은 `MenteeQueries.of_student`(멘티 목록과 같은 기준) |
| `mentoring/application/mentee_queries.py` | 페이지 묶음 계산을 `summarize`로 빼고 한 명용 `of_student` 추가 |
| `academy/presentation/roster_router.py` | `GET /admin/cohorts/{cohort_id}/students/{student_id}`(`academy.roster.read`, 기수 범위): 명단 항목 + `member` + `mentoring`(팀·1:1 계좌·대기 신청·예정·완료 세션 수) |
| `main.py` | `app.state.student_detail` 배선(B10) |
| `tests/api/test_mentoring_mentees.py` | 가입 계정·계좌 잔여·미가입 null·다른 기수 404 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A99)
- 기본·수강 + 멘토링 요약을 한 API로, 최근 신청·세션은 기존 `student_id` 필터 API를 쓴다.
- 다른 기수 수강 이력은 넣지 않는다.

## 발견한 문제와 해결
- `MenteeQueries`에 `list` 메서드가 있어 클래스 안 타입 주석의 `list[...]`가 메서드를 가리켰다. `builtins.list`·`Sequence`로 적었다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 912 passed

## 남은 작업
- FE-17c 수강생 목록·상세.
