# 39. P10-1 멘토링 팀 구성

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P10 (P10-1)
- 이전 기록: [38. P9-2 신청 가능 시간 계산·조회](38_p9_2_available_times.md)

## 배경
P10의 첫 PR이다. 운영진(매니저·조교)이 기수·유형별로 멘토링 팀을 만들고 담당 멘토와 팀원을 정한다. 팀은 팀 시간 계좌(P10-2)와 팀 신청(P11)의 단위가 된다. P10을 시작하기 전에 결정 사항을 모두 확인받았다(A39).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `mentoring/domain/team.py` | `MentoringTeam`: 팀 번호·이름(50자, 없으면 "N팀")·담당 멘토·팀원 목록. 팀원 추가·제거 규칙 |
| `mentoring/infrastructure/models/team.py`, `migrations/models/14_…` | `mentoring_teams`, `mentoring_team_members` + raw SQL(`(id, period_type)` 유니크, 팀원 복합 FK `ON DELETE CASCADE`, 유형 check, 팀 번호 > 0, 기본값) |
| `mentoring/infrastructure/repositories.py` | `TortoiseMentoringTeamRepository`: 팀과 팀원을 함께 저장(팀원 차이만 반영). 같은 유형 다른 팀 소속이면 409, 계좌·신청이 참조하면 삭제 409 |
| `mentoring/application/team_service.py` | `MentoringTeamService`: 생성·수정·삭제, 팀원 추가·제거, 팀 미배정 수강생, 내 팀, 감사 로그 |
| `academy/application/student_queries.py` | "수강 중" = ENROLLED이면서 원천에서 삭제되지 않은 등록. 기수 수강생·회원 등록·묶음 조회 |
| `mentoring/presentation/team_router.py` | API (아래 표) |

| 메서드 | 경로 | 권한 |
| --- | --- | --- |
| GET / POST | `/api/v1/admin/cohorts/{cohort_id}/mentoring-teams?period_type=` | `mentoring.team.manage` 기수 범위(매니저·조교). 목록은 페이징 없음 |
| GET | `…/mentoring-teams/unassigned-students?period_type=` | 같음. 그 유형 팀이 없는 수강 중 수강생 |
| PATCH / DELETE | `…/mentoring-teams/{team_id}` | 이름·담당 멘토 / 삭제(사용 중이면 409 `team_in_use`) |
| POST / DELETE | `…/mentoring-teams/{team_id}/members[/{student_id}]` | 팀원 추가·제거 |
| GET | `/api/v1/me/mentoring-teams` | 본인. 수강생은 소속 팀(멘토 표시 이름만, 팀원 이름), 멘토는 담당 팀 |

## 주요 결정 (사용자 결정, A39)
- **PR 분할:** P10-1 팀 구성, P10-2 시간 계좌·지급·조회·수강 종료 처리
- **팀 생성:**
  - 팀 멘토링을 허용한 기수에서만 만든다. 설정이 없으면 404, 허용 안 함이면 422 `team_mentoring_not_allowed`다.
  - 담당 멘토는 그 기수·유형의 활성 배정이어야 하고, 언제든 바꿀 수 있다. 이미 잡힌 신청·세션은 기존 멘토로 남는다(P11).
- **팀원:** 그 기수 수강 중이면 가입 여부와 무관하게 넣을 수 있다. 미가입 명단도 미리 팀을 짤 수 있다.
- **삭제:** 팀은 계좌·신청이 없을 때만 지운다. 팀원은 언제든 넣고 뺀다.
- **API:** 팀 목록은 페이징 없이 준다. 팀 미배정 수강생 목록과 내 팀 조회를 둔다.
- **수강 종료 처리:** 수강 중이 아니게 된 팀원을 자동으로 빼는 작업은 P10-2에 넣는다(명단 동기화 후 작업에서 1:1 잔여 회수와 함께 처리).

## 구현 세부
- **팀 번호:** 기수×유형별 최댓값 + 1이다. 동시 생성은 기수 멘토링 설정 행을 `SELECT … FOR UPDATE`로 잠가 직렬화한다(팀 생성에는 설정이 꼭 있어야 하므로).
  - 중간 번호가 비어도 다시 채우지 않는다.
  - 가장 큰 번호의 팀이 지워지면 그 번호는 다음 팀이 쓴다. 지울 수 있는 팀은 계좌·신청이 없는 팀이라 기록이 섞이지 않는다.
- **같은 유형 중복 소속:** 서비스 검사와 DB 유니크(`student_id, period_type`)로 이중으로 막는다. 팀원 유형과 팀 유형이 다르면 복합 FK가 막는다.
- **"수강 중" 기준:** A39에서 원천 삭제도 수강 종료로 보기로 해서, `is_enrolled`에 원천 삭제 제외를 더했다. 신청 가능 시간 조회 권한(A37)도 같은 기준을 쓴다.
- **쿼리 수:** 목록 응답은 팀·팀원·멘토·회원·수강생을 각각 한 번씩 묶어 조회한다. 팀 수와 관계없이 쿼리 수가 일정하다.

## 검증
- 단위:
  - 도메인: 이름(공백·50자)·번호·표시 이름, 팀원 중복·제거, 멘토 변경
  - 서비스: 번호 부여, 중복 소속 409, 미배정 멘토·다른 유형, 수강 종료·원천 삭제·다른 기수 수강생, 팀 멘토링 미허용·설정 없음, 수정·팀원·미배정 목록, 사용 중 삭제 409, 감사 로그, 내 팀
- 통합(PostgreSQL): 팀 왕복과 팀원 동기화, 다음 번호, 다른 유형 팀 소속 허용, 같은 유형 중복 409(트랜잭션 롤백), 복합 FK 위반, 삭제 시 팀원 CASCADE
- API:
  - 미배정 목록(가입 여부 표시) → 생성(멘토 실명·표시 이름) → 수강 종료 팀원 422 → 추가 → 중복 409 → 이름 변경 → 팀원 제거 → 목록
  - 내 팀(수강생은 멘토 실명 없음, 멘토는 담당 팀) → 삭제
  - 규칙·권한: 미배정 멘토·다른 유형, 팀 멘토링 미허용, 조교 200·다른 기수 403, 수강생 403, 비로그인 401
- 전체 655 passed (compose `api` 컨테이너, ruff·ruff format·mypy·mypy tests·lint-imports 통과)
- 마이그레이션 왕복: upgrade → migrate("No changes detected") → downgrade -v 14 → upgrade. DBML `@dbml/core` 11 검증
- 코드 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했다(649 → 653 → 655 passed)

## 남은 작업
- P10-2: 시간 계좌·원장·지급·조정·조회, 명단 동기화 후 수강 종료 처리(팀에서 빼기, 1:1 잔여 회수)
- P11: 팀 신청은 담당 멘토에게만, 멘토 변경 시 기존 신청·세션 유지
