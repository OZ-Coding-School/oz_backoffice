# OZ 통합 백오피스

오즈코딩스쿨 운영에 쓰던 개별 도구 5개(`prev_tools/`: Auto_monitor, mentor, ucansign, vacation, oz_discord_admin)를 PostgreSQL 기반의 단일 백오피스로 통합하는 모노레포. 백엔드(`apps/backend`, FastAPI)와 프론트엔드(`apps/frontend`, React)로 나뉜다. 1단계로 멘토링 기능을 먼저 이전한다.

| 문서 | 내용 |
| --- | --- |
| `docs/decisions.md` | 확정된 결정 전체 (다른 문서와 다르면 이 문서가 우선) |
| `docs/database_schema_v2.dbml` | 현재 DB 스키마 |
| `docs/implement_plans/` | 구현 계획 (멘토링 1단계: `mentoring_phase1_backend.md`) |
| `docs/implement_descriptions/` | 구현 기록 |
| `docs/analysis/` | 기존 서비스 분석 (로컬 전용, `.gitignore`) |
| `apps/*/CLAUDE.md` | 앱별 기술 스택·명령어·구조 규칙 |

## Git 브랜치 전략 (Git Flow + GitHub Flow)

| 브랜치 | 용도 | 분기 기준 | 병합 대상 |
| --- | --- | --- | --- |
| `main` | 운영 배포 브랜치. 병합 시 자동 배포 (배포 워크플로 `.github/workflows/deploy.yml`은 배포 대상 확정 후 구성 예정) | - | - |
| `develop` | 다음 배포를 모으는 통합 브랜치 | `main` | `main` (배포 PR) |
| `feature/<설명>` | 기능 추가 | `develop` | `develop` |
| `fix/<설명>` | 버그 수정 | `develop` | `develop` |
| `docs/<설명>` | 문서 작성·수정 | `develop` | `develop` |
| `build/<설명>` | 빌드·배포 구성 (Dockerfile, compose, CI 워크플로, 의존성) | `develop` | `develop` |
| `chore/<설명>` | 코드 동작에 영향 없는 기타 작업 (설정, 정리) | `develop` | `develop` |
| `test/<설명>` | 테스트 코드 추가·수정 | `develop` | `develop` |

### 규칙

- `main`, `develop`에는 **직접 커밋·push하지 않는다.** 모든 변경은 작업 브랜치에서 PR로 병합한다.
- 작업 브랜치는 항상 최신 `develop`에서 만든다.
  ```bash
  git switch develop && git pull origin develop
  git switch -c feature/role-automation-dry-run
  ```
- 브랜치 이름: `<유형>/<영문 소문자-케밥-케이스>` (예: `feature/google-oauth-login`, `fix/faq-attachment-upload`)
  - 이슈가 있으면 번호를 앞에 붙인다: `feature/12-google-oauth-login`
- PR은 `develop`을 base로 연다. 리뷰·확인 후 병합하고, 병합된 작업 브랜치는 삭제한다.
- **PR을 병합하기 전에 작업 브랜치를 최신 `develop` 위로 rebase한다.** 병합 시점에 작업 브랜치가 `develop`의 최신 커밋을 모두 포함하고 있어야 한다. (PR을 만들 때, 그리고 병합 직전에 `develop`이 앞서 있으면 다시 rebase)
  ```bash
  git fetch origin
  git rebase origin/develop                 # 충돌이 나면 해결 후 git add → git rebase --continue
  # rebase 후 로컬 검사(lint·테스트)를 다시 실행해 통과를 확인한다
  git push --force-with-lease               # rebase로 이력이 바뀌므로 강제 push (--force 대신 --force-with-lease)
  ```
  - rebase 후 push하면 CI가 다시 실행된다. **CI가 최신 `develop` 기준으로 통과한 뒤** 병합한다.
  - rebase는 본인 작업 브랜치에만 한다. `main`·`develop`은 rebase하거나 강제 push하지 않는다.
  - 다른 사람과 함께 쓰는 작업 브랜치를 rebase할 때는 미리 알리고, 받는 쪽은 `git pull --rebase`로 맞춘다.
  - 병합 방식은 merge commit을 사용한다. (rebase로 최신화한 뒤 병합하므로 이력이 `develop` 최신 커밋 위에 이어진다)
- 배포는 `develop` → `main` PR로만 한다. `main`에 병합되면 자동 배포된다.
- 운영 중 긴급 수정이 필요하면 `main`에서 `fix/<설명>`을 만들어 `main`에 PR로 병합하고, 같은 변경을 `develop`에도 반영한다.
- 한 브랜치에는 한 가지 목적의 변경만 담는다. 앱(`apps/backend`, `apps/frontend`)이 다른 변경은 가능하면 브랜치를 나눈다.

### 커밋 메시지

`<타입>: <한글 설명>` 형식으로 쓴다. 타입은 브랜치 유형과 맞춘다.

- 커밋 템플릿 `.github/commit_template.txt`를 사용한다. 저장소를 clone한 뒤 루트에서 한 번 설정한다.
  ```bash
  git config commit.template "$(git rev-parse --show-toplevel)/.github/commit_template.txt"
  ```
- `git commit -m`으로 커밋하는 경우에도 템플릿의 형식(제목 50자 이내·마침표 없음, 제목과 본문 사이 빈 줄, 본문은 무엇을·왜)을 따른다.

| 타입 | 용도 |
| --- | --- |
| `feat` | 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 |
| `build` | 빌드·의존성·Docker 구성 |
| `ci` | GitHub Actions 등 CI/CD 워크플로 (브랜치는 `build/`) |
| `chore` | 기타 작업 |
| `test` | 테스트 |
| `refactor` | 동작 변경 없는 코드 구조 개선 (브랜치는 `feature/` 또는 `chore/`) |
| `hotfix` | 운영(`main`) 대상 긴급 수정 (브랜치는 `main`에서 만든 `fix/`) |

예: `feat: 역할부여 자동화 dry_run 옵션 추가`, `fix: FAQ 첨부파일 업로드 시 bytes 변환 누락 수정`

## 로컬 검사와 CI

PR을 올리기 전에 변경한 앱의 검사를 로컬에서 모두 통과시킨다. CI(`.github/workflows/ci.yml`)는 `main`·`develop` 대상 PR과 push에서 **변경된 앱만** 같은 검사를 실행한다.

로컬 개발 환경은 루트에서 `docker compose up -d --build`로 띄운다 (API http://localhost:8000/docs).

| 앱 | 검사 | 명령 |
| --- | --- | --- |
| `apps/backend` | 린트·포맷 | `docker compose exec api ruff check .`, `docker compose exec api ruff format --check .` |
| | 타입 | `docker compose exec api mypy`, `docker compose exec api mypy tests` |
| | 계층 의존 규칙 | `docker compose exec api lint-imports` |
| | 테스트 (통합 포함) | `docker compose exec api pytest` |
| | (호스트 실행 시) | `apps/backend`에서 `uv run ruff check .` 등 같은 명령에 `uv run`을 붙이고, 테스트는 `TEST_DATABASE_URL=postgres://oz:oz@localhost:5432/oz_backoffice_test uv run pytest` |
| `apps/frontend` | 린트·타입·단위 테스트·빌드·E2E | `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run e2e` (프론트엔드 세팅 후, 앱 디렉터리에서) |

- 백엔드 CI는 PostgreSQL 서비스 컨테이너로 통합 테스트까지 실행한다. compose의 `api` 컨테이너에서도 통합 테스트까지 실행된다.
- 문서(`docs/`)만 바꾼 PR은 CI 검사가 실행되지 않는다.

### Pull Request

- PR 본문은 `.github/pull_request_template.md` 양식을 따른다. GitHub 웹에서 PR을 열면 자동으로 채워지며, `gh pr create`로 만들 때도 같은 항목(개요, 변경 유형, 변경 대상, 주요 변경 사항, 테스트/확인 방법, 관련 이슈, 체크리스트, 참고 사항)을 모두 작성한다.
- PR 제목은 커밋 메시지 제목 규칙(`<타입>: <한글 설명>`)과 같은 형식으로 쓴다.
- 체크리스트에서 해당하지 않는 항목은 지우지 말고 체크하지 않은 채로 두거나 "해당 없음"을 적는다.

## 구현 기록

기능 구현이 끝나면 **같은 PR에서** 구현 기록을 남긴다. 상세 양식은 `docs/implement_descriptions/README.md`를 따른다.

- 위치: `docs/implement_descriptions/backend/` (백엔드·저장소 공통 작업), `docs/implement_descriptions/frontend/` (프론트엔드·Vercel 배포)
- 파일: `NN_<작업명>.md` — 해당 디렉터리의 마지막 번호 다음 번호로 작성하고, 디렉터리 `README.md` 목록에 한 줄 추가
- 내용: 상태·관련 PR, 배경, 구현 내용(주요 파일), 주요 결정(사용자 결정 포함), 발견한 문제와 해결, 검증, 남은 작업
- 상태는 PR을 열 때 "PR 진행 중"으로 쓴다. **사용자가 작업 완료(병합)를 컨펌하면 그 PR에 바로** 기록 상태·디렉터리 `README.md` 목록을 "완료"로 바꾸고, 완료 시점에 확정된 내용(검증 결과, 사용자 확인, 남은 작업)도 반영해 커밋한 뒤 병합한다. 다음 작업 PR로 미루지 않는다.
  - 순서: PR 생성 → PR 번호 기록 커밋 → 사용자 컨펌 → "완료" 반영 커밋 → (develop이 앞서 있으면 rebase) → CI 통과 → 병합
  - 관련 계획 문서의 상태·체크리스트(`docs/implement_plans/**`)도 같은 커밋에서 완료로 갱신한다.
- 이미 작성된 기록의 내용은 바꾸지 않는다. 같은 기능을 다시 고치면 새 번호로 기록하고 이전 기록을 링크한다.
