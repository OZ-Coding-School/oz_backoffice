## 개요

<!-- 이 PR에서 무엇을, 왜 변경했는지 1~3줄로 작성해주세요. -->

## 변경 유형

- [ ] feat: 기능 추가
- [ ] fix: 버그 수정
- [ ] hotfix: 운영(`main`) 대상 긴급 수정
- [ ] docs: 문서
- [ ] build / ci: 빌드·배포 구성
- [ ] chore: 기타 작업
- [ ] test: 테스트
- [ ] refactor: 코드 구조 개선

## 변경 대상

- [ ] `apps/backend`
- [ ] `apps/frontend`
- [ ] `docs` (스키마 `database_schema_v2.dbml`, 결정 `decisions.md`, 계획·기록)
- [ ] 인프라·배포 구성 (`.github`, `docker-compose*.yml`, `infra/`)

## 주요 변경 사항

<!-- 리뷰어가 집중해서 봐야 할 변경을 나열해주세요. -->
-

## 테스트 / 확인 방법

<!-- 어떻게 확인했는지, 리뷰어가 어떻게 재현할 수 있는지 작성해주세요. -->
-

## 관련 이슈

<!-- Closes #번호 / Refs #번호 -->

## 체크리스트

- [ ] base 브랜치가 맞다 (작업 브랜치 → `develop`, 배포는 `develop` → `main`, 긴급 수정은 `fix/*` → `main`)
- [ ] 최신 `develop` 위로 rebase했고, rebase 후 CI가 통과했다
- [ ] 커밋 메시지가 `<타입>: <한글 설명>` 규칙을 따른다
- [ ] 토큰·API 키·`.env` 등 시크릿이 포함되지 않았다
- [ ] 구현 기록(`docs/implement_descriptions/<backend|frontend>/NN_<작업명>.md`)을 작성했고, 관련 계획 문서(`docs/implement_plans/`)의 상태를 갱신했다
- [ ] 새로 확정한 결정이 있으면 `docs/decisions.md`에 추가했다
- [ ] (backend) `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `pytest`(통합 테스트 포함)를 로컬에서 통과했다
- [ ] (backend) 스키마 변경 시 DBML(`docs/database_schema_v2.dbml`)·Tortoise 모델·aerich 마이그레이션(raw SQL 제약 포함)을 함께 수정했다
- [ ] (backend) 다른 컨텍스트의 `infrastructure`/`presentation`을 직접 import하지 않았다 (`application` 서비스로만 호출)
- [ ] (frontend) `lint`, `typecheck`, `test`, `build`, `e2e`를 로컬에서 통과했다
- [ ] (frontend) API 변경에 맞춰 MSW 핸들러와 API 타입을 함께 수정했다

## 참고 사항

<!-- 스크린샷, 배포 시 주의사항(.env 추가, 마이그레이션 순서 등), 후속 작업 등 -->
