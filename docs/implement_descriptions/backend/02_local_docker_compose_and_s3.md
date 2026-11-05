# 02. docker compose 로컬 개발 환경과 S3 에뮬레이터

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 이전 기록: [01. 백엔드 프로젝트 세팅과 CI](01_backend_project_setup.md)

## 배경
- 로컬 개발의 기본 실행 방식을 docker compose로 정했다 (decisions R6).
- 객체 저장소를 GCS에서 AWS S3로 바꿨다 (C5~C7). 로컬·CI에서 쓸 S3 에뮬레이터가 필요했다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| 루트 `docker-compose.yml` | PostgreSQL 17, Redis 7, S3 에뮬레이터 `s3`(floci 2.4.0), 버킷 초기화 `s3-init`, 백엔드 `api` / `worker` / `scheduler` |
| `api` 서비스 | `Dockerfile`의 `dev` 타깃. `src`, `tests`, `migrations`, `pyproject.toml`을 마운트하고 `uvicorn --reload`로 실행, `/health` 헬스체크 |
| `worker` / `scheduler` 서비스 | `api`가 빌드한 이미지를 `pull_policy: never`로 재사용해 taskiq 실행 |
| 백엔드 공통 환경 | `apps/backend/.env`를 읽되, DB·Redis·S3 주소와 `TEST_DATABASE_URL`은 서비스 이름(`postgres`, `redis`, `s3`) 주소로 덮어쓴다. presigned URL용 `S3_PUBLIC_ENDPOINT_URL`은 `http://localhost:4566` |
| `s3` 서비스 | floci 2.4.0, `FLOCI_SERVICES_S3_ENFORCE_AUTH=true`(서명 검증·비공개 버킷), `FLOCI_STORAGE_MODE=persistent` + `s3-data` 볼륨 |
| `s3-init` 서비스, `infra/s3/init.sh`, `cors.json` | `amazon/aws-cli:2.31.0`. 에뮬레이터 대기 → 버킷 생성(있으면 건너뜀) → CORS 설정 (멱등). 백엔드 서비스는 이 작업이 성공해야 뜬다 |
| `infra/postgres/init/01-extensions-and-test-db.sql` | `btree_gist` 확장, 통합 테스트 DB `oz_backoffice_test` 생성 |
| `apps/backend/Dockerfile`, `.dockerignore` | uv 기반 멀티 스테이지 이미지. `dev`(dev 의존성 + tests 포함, reload) / `prod`(런타임 의존성만, non-editable 설치). API / 워커 / 스케줄러 공용 |
| `apps/backend/.env.example` | 로컬 설정 예시 (compose가 덮어쓰는 값 안내, S3 변수) |

## 주요 결정
- 로컬 개발 기본 실행은 docker compose, 호스트 uv 실행은 IDE·디버거용 대안 (사용자 결정, R6)
- 객체 저장소 AWS S3: 비공개 버킷 1개 + prefix, presigned POST 업로드, presigned GET 다운로드, 엔드포인트는 서버용·브라우저용 두 개 (사용자 결정, C5~C7). 클라이언트는 aioboto3 (B8, 어댑터 구현 시 추가)
- 로컬·CI 에뮬레이터 floci 2.4.0, 인증 강제 (사용자 결정, R7)
  - LocalStack 최신(2026.10)은 인증 토큰 없이 실행되지 않았다(실측). 그래서 사용자가 제시한 floci와 MiniStack을 실측 비교했다.
  - 백오피스가 쓸 S3 시나리오 16개를 두 이미지에서 실측했다. presigned POST 크기·타입 정책, presigned GET·만료, CORS preflight, 서명 검증, 비공개 버킷, aioboto3, 멀티파트, Range가 포함된다.
  - 두 도구 모두 인증 옵션을 켜면 16/16을 통과했다. 기본값에서는 서명을 검증하지 않았다.

    | | floci 2.4.0 | MiniStack 1.5.37 | LocalStack 4.14 (기준) |
    | --- | --- | --- | --- |
    | 인증 옵션 켬 | 16/16 | 16/16 | 11/16 (옵션 없음) |
    | 이미지 / 유휴 메모리 / 첫 응답 | 93MB / 23MiB / 0.5초 | 68MB / 37MiB / 1.1초 | 456MB / 115MiB / 2.2초 |
    | 재시작 후 데이터 유지 | 옵션 1개로 객체·버킷 설정 유지 | 옵션 2개 필요 | — |

  - 커뮤니티·호환성 테스트 규모, 고정 릴리스 주기, 단순한 데이터 유지 설정에서 floci를 골랐다. 실측 스크립트와 비교 문서는 저장소에 두지 않는다(사용자 결정).
- 버킷·CORS 초기화는 에뮬레이터 init 훅이 아니라 `aws-cli` 원샷 컨테이너로 한다 (사용자 결정, R8)

## 발견한 문제와 해결
- `pyproject.toml`의 `readme = "CLAUDE.md"` 때문에 이미지 빌드 시 프로젝트 설치에 CLAUDE.md가 필요했다. 패키지로 배포하지 않으므로 `readme` 설정을 제거했다.
- `api` / `worker` / `scheduler`가 모두 `build`를 가지면 같은 이미지 태그를 동시에 빌드하다 `image already exists`로 실패했다. 빌드는 `api`만 하도록 바꿨다.
- floci 이미지에는 curl이 없다. 그래서 `s3-init`이 S3 API가 응답할 때까지 재시도한다(최대 60초).
- 두 에뮬레이터 모두 **기본값에서는 서명을 검증하지 않는다**(위조 서명·서명 없는 요청 통과). 그래서 인증 옵션을 반드시 켠다.
- 모델이 아직 없어 api·worker 기동 로그에 `Module ... has no models` RuntimeWarning이 컨텍스트 수만큼 찍힌다. 첫 모델이 생기면 사라진다.

## 검증 (Docker 27.4, 2026-11-05)
- `docker compose up -d --build`: 7개 서비스 기동. `s3-init` 정상 종료(0) 후 백엔드 기동, `api` healthy
- `/health` 200, `/health/ready` 200 (`database`·`redis` ok). worker `Listening started`, scheduler `Startup completed`
- `docker compose exec api coverage run -m pytest`: **22개 모두 통과 (통합 테스트 3개 포함, 실제 PostgreSQL)**. coverage 85% (`uow.py` 89%)
- 컨테이너 안 `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`: 통과
- `btree_gist` 확장: `oz_backoffice`, `oz_backoffice_test` 모두 설치 확인
- 소스 변경 시 `api` 자동 재시작(WatchFiles) 후 `/health` 200 확인
- `prod` 타깃 빌드: `app.main` import 성공, dev 의존성(pytest) 미포함 확인
- S3 (floci):
  - 호스트 브라우저 경로(`localhost:4566`)에서 확인한 결과:
    - CORS preflight 200 (`ACAO=http://localhost:5173`)
    - presigned POST 업로드 204, presigned GET 200
    - 서명 없는 GET 403
  - 컨테이너 내부 경로(`http://s3:4566`)에서 같은 객체를 `head-object`로 확인 (크기, Content-Type)
  - `s3` 재시작 후 객체 유지 확인, `s3-init` 재실행 시 "버킷 존재"로 멱등 확인
- GitHub Actions 실행 결과: PR에서 확인 후 기록

## 남은 작업
- S3 어댑터(`integrations/s3.py`, aioboto3) 구현 시(P6):
  - 위 S3 시나리오(presigned POST 정책·GET·만료, CORS, 서명 검증, 비공개 버킷, 멀티파트, Range)를 `tests/integration`의 호환성 테스트로 작성한다
  - CI에 floci 서비스 컨테이너와 버킷 초기화 단계를 추가한다
- 운영 배포 전 실제 AWS S3 스테이징 버킷에서 presigned POST/GET 스모크 테스트
