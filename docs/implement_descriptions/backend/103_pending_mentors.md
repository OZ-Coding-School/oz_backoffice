# 103. 가입 전 멘토와 멘토 계약 (BE-3w)

- 상태: PR 진행 중
- 관련 PR: (작성 후 기록)
- 관련 결정: `docs/decisions.md` A104 (F82, A23·A27 변경)
- 이전 기록: [102. 계약 화면 보완 (BE-3v)](102_contract_people.md)

## 배경
계약 메뉴를 따로 두지 않고 멘토 상세에서 계약을 관리하기로 했다(F82). 그러려면 멘토 계약이 항상 멘토에 속해야 하고, 아직 가입하지 않은 사람과의 계약은 계정 없는 '가입 전 멘토'에 붙어야 한다(A104).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `educator/domain/profiles.py` | `Mentor.user_id` 선택값, 연락처 `contact_name`·`contact_phone`, `Mentor.pending()`, `is_registered`, `account_id`(가입한 멘토의 회원 id, 아니면 `mentor_not_registered`), `register()`(A105에서 사용), `update_contact()`, 가입 전이면 활성화 금지 |
| `educator/domain/entities.py` | 멘토 계약의 연결 해제 금지(`mentor_contract_unlink_forbidden`) |
| `educator/application/contracts.py` | 만들 때 멘토 정하기(지정 → 같은 사람 하나 → 새 가입 전 멘토, 둘 이상이면 `ambiguous_mentor`), 계약자 정보를 고치면 가입 전 연락처 맞추기, 연결된 계약의 유형 변경 금지, 계약이 없는 가입 전 멘토 지우기(삭제·옮기기 후) |
| `educator/infrastructure/models.py`, `migrations/models/34_*_pending_mentors.py` | `mentors.user_id` NULL 허용, 연락처 열·색인, CHECK `check_mentor_account_or_contact`·`check_mentor_pending_inactive` |
| `educator/infrastructure/repositories.py` | 같은 사람 찾기(회원 이름·휴대폰 또는 연락처), 멘토 삭제, 목록 `registered` 필터·연락처 검색 |
| `educator/presentation/admin_router.py` | 계약 생성 `mentor_id` |
| `educator/presentation/mentor_router.py` | 목록 `status=active\|inactive\|pending`, 응답 `is_registered`, 가입 전이면 이름·휴대폰은 연락처·이메일 null |
| `mentoring/**`, `composition/*` | 배정·신청·세션·채팅·정산의 멘토는 가입한 멘토이므로 회원 id를 `account_id`로 읽는다 |
| `docs/database_schema_v2.dbml` | `mentors` 열·색인·CHECK |
| 테스트 | 단위(멘토 정하기·연락처 맞추기·옮기기·빈 멘토 삭제), API(`test_pending_mentors.py`: 목록·단건·검색·활성화 금지·삭제, DB CHECK) |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성, 멘토 테스트 데이터에 `is_registered` |

## 주요 결정 (사용자 결정, A104)
- 멘토 계약을 만들 때 가입 전 멘토를 자동으로 만들고, 같은 사람이면 기존 멘토에 붙인다.
- 가입 전 상태를 따로 둔다. 연결 해제 대신 다른 멘토로 옮기기만 한다. 계약이 없는 가입 전 멘토는 지운다.
- 기존 미연결 멘토 계약은 옮기지 않는다. 강사 계약은 이번에 바꾸지 않는다.

## 발견한 문제와 해결
- `user_id`를 선택값으로 바꾸면 멘토링 코드 29곳이 타입 오류를 냈다. 배정·신청·세션·채팅의 멘토는 모두 가입한 멘토이므로 `account_id` 속성(없으면 오류)으로 읽게 했다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 919 passed
- 마이그레이션: `aerich upgrade` → `aerich migrate`(No changes detected) → `aerich downgrade -v 34` → `aerich upgrade`, DBML 파서 검증

## 남은 작업
- BE-3x 가입 연결(A105), FE-18b, FE-15a 보완.
