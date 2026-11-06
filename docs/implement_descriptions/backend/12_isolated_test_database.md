# 12. 테스트 DB를 격리된 TortoiseContext와 전용 DB로 관리

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: 해당 없음 (테스트 기반 정리)
- 이전 기록: [03. P1-1 identity·audit 모델과 첫 마이그레이션](03_p1_1_identity_audit_models.md) (기존 테스트 DB 픽스처를 만든 기록)

## 배경
사용자가 `tests/conftest.py`의 DB 의존성 문제를 지적했다. Tortoise 테스트 문서(https://tortoise.github.io/contrib/unittest.html)와 사용자가 이전 프로젝트에서 쓴 conftest를 참고해 고쳐 달라고 요청했다.

기존 방식의 문제는 네 가지였다.
- **전역 상태:** aerich `Command`를 돌리려고 `Tortoise.init(..., _enable_global_fallback=True)`로 전역 연결을 열었다. Tortoise 1.x가 권장하는 격리된 `TortoiseContext`와 맞지 않았다.
- **위험한 초기화:** `TEST_DATABASE_URL`이 가리키는 DB의 `public` 스키마를 그대로 `DROP`했다. 개발 DB 주소를 잘못 넣으면 개발 데이터가 사라진다.
- **명시적 픽스처 의존:** 통합 테스트 모듈마다 `usefixtures("db")`를 붙여야 했다. 빠뜨리면 연결 오류가 나거나 데이터가 섞인다. 실제로 `test_unit_of_work.py`는 `database`만 써서 테스트 후 TRUNCATE를 건너뛰었다.
- **환경 의존 skip:** `TEST_DATABASE_URL`이 없으면 통합 테스트가 조용히 skip됐다.

## 구현 내용

| 경로 | 변경 |
| --- | --- |
| `tests/conftest.py` | `tortoise_db`(세션, autouse): 테스트 DB를 지우고 새로 만든다 → 격리된 `TortoiseContext`를 연다 → `btree_gist` 확장을 만든다 → aerich 마이그레이션 파일의 `upgrade()` SQL을 번호 순으로 적용한다 → 세션이 끝나면 DB를 지운다 |
| | `clean_tables`(테스트마다, autouse): 테스트가 끝나면 모든 모델 테이블을 TRUNCATE한다 |
| | DB 생성·삭제는 관리 DB(`postgres`)에 asyncpg로 접속해 한다. 이름이 `_test`로 끝나지 않으면 거부한다 |
| | `TEST_DATABASE_URL`이 없으면 로컬 compose postgres(`localhost:5432/oz_backoffice_test`)를 쓴다 |
| `tests/integration/**` | `usefixtures("db"/"database")`를 지웠다. `Tortoise.get_connection` → `connections.get("default")` |
| `.github/workflows/ci.yml` | 테스트 DB 확장을 미리 만드는 단계를 지웠다(별도 `ci:` 커밋) |
| `apps/backend/CLAUDE.md` | 테스트 DB 규칙과 호스트 실행 설명을 갱신했다 |

## 주요 결정
- 사용자 코드처럼 세션 DB와 테스트별 정리를 **autouse**로 둔다. 테스트는 DB 픽스처를 따로 요청하지 않는다. 그래서 단위 테스트를 돌릴 때도 PostgreSQL이 떠 있어야 한다. compose와 CI는 항상 DB를 띄우므로 문제가 없다. 대신 skip으로 통합 테스트를 놓치는 일이 없어진다.
- 문서의 `tortoise_test_context`는 쓰지 않는다. 같은 구성(`TortoiseContext` + 루프 전환 경고 무시)을 직접 열고, 스키마는 `generate_schemas()` 대신 **마이그레이션 SQL**로 만든다. `generate_schemas()`로는 마이그레이션에만 있는 제약(CHECK, 부분 유니크, `NULLS NOT DISTINCT`, 자기 참조 FK, DB 기본값)이 빠진다. 그러면 DB 제약 테스트가 운영 스키마를 검증하지 못한다. 사용자 코드처럼 CHECK를 모델에서 읽어 따로 추가하는 방식도 검토했다. 하지만 이 프로젝트는 raw SQL 제약이 많아 마이그레이션과 내용이 어긋날 수 있어 택하지 않았다.
- 마이그레이션은 aerich `Command`가 아니라 각 파일의 `upgrade()` SQL을 직접 실행한다. aerich가 요구하던 전역 연결 우회가 필요 없어진다.
- DB 생성에 Tortoise의 `_create_db`를 쓰지 않는다. `_create_db`는 사용자 이름과 같은 DB(`oz`)로 접속해 실패했다. 삭제와 같은 방식으로 관리 DB에서 직접 만든다.

## 발견한 문제와 해결
- `_create_db=True`가 `database "oz" does not exist`로 실패했다. 위 결정대로 관리 DB에서 `CREATE DATABASE`를 실행하도록 바꿨다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **188개 통과**(2.2초)
- 세션이 끝난 뒤 `oz_backoffice_test` DB가 지워졌는지 확인했다
- 파일 단위 실행(UnitOfWork, 역할, CLI·identity)도 통과했다
- 호스트에서 `TEST_DATABASE_URL` 없이 `uv run pytest` 실행: 188개 통과(로컬 compose postgres 사용)

## 남은 작업
- 없음
