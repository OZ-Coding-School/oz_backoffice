# 102. 계약 화면 보완 (BE-3v)

- 상태: PR 진행 중
- 관련 PR: #163
- 관련 결정: `docs/decisions.md` A103 (F81, A25·A27)
- 이전 기록: [101. 멘토 단건 조회 (BE-3u)](101_mentor_detail.md)

## 배경
FE-18b 계약 화면은 표·패널에 담당 직원과 연결된 프로필 이름을 보여 주고, 담당 직원을 검색해 고르며, 멘토 상세에 그 멘토의 계약 탭을 둔다(F81). 계약 응답에는 id만 있고, 직원 목록은 조직 권한이 있어야 하며, 멘토별 필터가 없어 보완한다(A103).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `educator/application/contract_people.py` | 포트 `ContractPeopleReader`와 `ContractPeople`·`LinkedPerson`·`ManagerCandidate` |
| `app/composition/contract_people.py` | 담당 직원·연결된 멘토(표시 이름 반영)·강사 이름을 한 번에 모으고, 담당 직원 후보를 일치 순으로 정렬(검색어가 없으면 나를 맨 앞) |
| `educator/presentation/admin_router.py` | 계약 응답에 `manager_name`·`linked_profile`, 목록 `mentor_id` 필터, `GET /admin/contracts/manager-candidates?q=`(`educator.contract.manage`, 20개) |
| `educator/domain/repositories.py`, `infrastructure/repositories.py` | `ContractFilter.mentor_id`, 강사 id → 회원 id 조회 |
| `main.py` | `app.state.contract_people` |
| `tests/api/test_contract_people.py` | 이름(멘토 닉네임 표시·강사 실명), 멘토 필터, 후보 순서·나·권한 |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A103)
- 멘토 필터·담당 직원 후보·응답 이름 세 가지를 PR 하나로 먼저 병합한다.

## 발견한 문제와 해결
- 없음

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 915 passed

## 남은 작업
- FE-18b 계약 화면.
