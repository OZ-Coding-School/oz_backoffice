# 98. 수강생 상세 API (BE-3r)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #155
- 관련 결정: `docs/decisions.md` A99 (F73·F76, A10·A31)
- 이전 기록: [97. HRD 연결 정보 (BE-3q)](97_hrd_links.md)

## 배경
FE-17c 학사 > 수강생 패널은 기본·수강 정보와 다른 기수 수강 이력을 보여 준다(F76). 기수 명단 목록 API만 있어 수강생 한 명의 상세와 이력을 주는 API를 더한다(A99).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `academy/domain/repositories.py`, `infrastructure/repositories.py` | `StudentRepository.list_same_person`: 가입했으면 같은 회원, 가입 전이면 이름 + 휴대폰이 같은 명단(휴대폰이 없으면 없음), 자신 제외, 최근 등록부터. 원본에서 빠진 행도 포함 |
| `academy/application/roster_queries.py` | `cohort_student`: 그 기수의 수강생이 아니면 404 `student_not_found` |
| `academy/presentation/roster_router.py` | `GET /admin/cohorts/{cohort_id}/rosters/{student_id}`(`academy.roster.read`, 기수 범위): 명단 항목 + `other_enrollments`(수강생 id·기수 id·운영과정 이름·기수 번호·수강 상태·등록일·종료일) |
| `tests/api/test_roster_sync_api.py` | 가입 회원·이름 + 휴대폰 기준 이력, 다른 기수 수강생 404, 담당이 아닌 기수 403 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A99)
- 같은 사람은 가입 연결이면 회원, 아니면 이름 + 휴대폰(A31 가입 매칭과 같은 기준).
- 수강 상태는 이번에 조회만.

## 발견한 문제와 해결
- 학생 id만으로는 기수 범위 권한을 검사할 수 없어 경로에 기수를 넣었다(`/cohorts/{cohort_id}/rosters/{student_id}`).

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 912 passed

## 남은 작업
- FE-17c 수강생 화면.
