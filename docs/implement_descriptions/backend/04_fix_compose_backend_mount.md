# 04. docker compose 백엔드 마운트 수정

- 상태: 완료 (2026-11-05 병합)
- 관련 PR: #7
- 이전 기록: [02. docker compose 로컬 개발 환경과 S3 에뮬레이터](02_local_docker_compose_and_s3.md)

## 배경
P1-1 작업 중 호스트에서 `apps/backend/pyproject.toml`을 고쳤다. 그러자 컨테이너 안의 파일이 예전 길이에서 잘린 채로 보여 ruff·mypy·pytest가 TOML 파싱 오류로 실패했다. 기록 02의 compose가 `pyproject.toml`을 **단일 파일로 바인드 마운트**하고 있었고, Docker Desktop에서는 이 방식이 파일 크기 변경을 제대로 반영하지 못한다.

## 구현 내용

| 경로 | 변경 |
| --- | --- |
| `docker-compose.yml` | 백엔드 서비스 마운트를 `src`·`tests`·`migrations`·`pyproject.toml` 개별 마운트에서 `./apps/backend:/app` 디렉터리 마운트 하나로 변경 |
| `apps/backend/Dockerfile` | 가상환경 위치를 `/app/.venv`에서 `/opt/venv`로 옮김(`UV_PROJECT_ENVIRONMENT`, `PATH`). 디렉터리 마운트가 이미지의 가상환경을 가리지 않게 하기 위함 |
| `apps/backend/CLAUDE.md` | api 서비스 설명 갱신 |

## 주요 결정
- 익명 볼륨으로 `/app/.venv`를 보존하는 방법은 쓰지 않았다. 의존성을 바꾸고 이미지를 다시 빌드해도 예전 볼륨이 남아 낡은 가상환경을 쓰게 되는 함정이 있기 때문이다. 대신 가상환경을 마운트 경로 밖에 둔다.
- 디렉터리 마운트로 호스트의 `apps/backend/.env`도 컨테이너에서 보이지만, DB·Redis·S3 주소는 compose `environment`가 덮어쓰므로 동작은 같다.

## 검증
- 컨테이너를 다시 만든 뒤 호스트에서 `pyproject.toml`을 고치고 바로 컨테이너에서 같은 내용이 보이는지 확인
- `docker compose exec api` 안에서 ruff, mypy, lint-imports, pytest 통과
- `prod` 타깃 빌드: `/opt/venv/bin/uvicorn`, `app.main` import 성공
- GitHub Actions (PR #7, run 41990132144): backend 잡 통과
- 사용자 확인: P1 진행 지시에 따라 CI 통과 후 병합

## 남은 작업
- 없음
