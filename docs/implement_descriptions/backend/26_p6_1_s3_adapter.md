# 26. P6-1 S3 어댑터와 S3 시나리오 통합 테스트

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P6 (P6-1)
- 이전 기록: [02. docker compose 로컬 개발 환경과 S3 에뮬레이터](02_local_docker_compose_and_s3.md)

## 배경
P6(S3 어댑터 + 교육 인력·계약)의 첫 PR이다. 계약서(PDF)와 프로필 사진을 비공개 버킷에 올리고 presigned URL로만 내려준다(decisions C5). 이번 PR은 그 공통 기반을 만든다. 하나는 S3 어댑터, 하나는 백오피스가 쓰는 S3 시나리오를 에뮬레이터로 검사하는 통합 테스트다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `app/integrations/s3.py` | `S3Storage`: `presign_post(key, content_type, max_bytes, now)`, `presign_get(key, download_name=)`, `head(key)`, `delete(key)`. 오류는 `StorageError`(503) |
| `app/core/storage.py` | `Settings` → `S3Settings`·`S3Storage` 조립 (`build_s3_storage`) |
| `tests/integration/storage/` | floci 테스트 전용 버킷 픽스처(`s3_bucket`, CORS 포함, 세션 끝에 삭제)와 S3 시나리오 테스트 |
| `tests/unit/integrations/test_s3.py` | 공개 엔드포인트 서명, 다운로드 파일 이름 헤더, 설정 변환 |
| `tests/conftest.py` | 테스트 `Settings`에 S3 설정 고정(테스트 버킷 `oz-backoffice-test`, `TEST_S3_ENDPOINT_URL`) |
| `docker-compose.yml` | 백엔드 서비스에 `TEST_S3_ENDPOINT_URL=http://s3:4566` |
| `.github/workflows/ci.yml` | 백엔드 잡에 floci 서비스 컨테이너(인증 강제)와 응답 대기 단계 |
| `pyproject.toml`, `uv.lock` | `aioboto3`, 개발 의존성 `types-aioboto3[s3]~=15.5.0` |

- **presigned POST:** `Content-Type`을 고정하고 `content-length-range`를 1 ~ `max_bytes`로 건다. 크기·타입 위반은 S3가 거부한다. 응답에 만료 시각(`expires_at`)을 담는다.
- **엔드포인트 분리 (C7):** 서버 호출은 `S3_ENDPOINT_URL`을 쓴다. presigned URL은 `S3_PUBLIC_ENDPOINT_URL`로 서명한다(없으면 서버 주소). 운영은 둘 다 비우면 AWS 기본 엔드포인트를 쓴다.
- **다운로드 이름:** `download_name`을 주면 `ResponseContentDisposition`을 붙인다. 형식은 `attachment; filename="<ASCII 대체>"; filename*=UTF-8''<퍼센트 인코딩>`이라 한글 파일 이름이 유지된다.
- 없는 객체의 `head`는 `None`을 돌려준다. 없는 객체를 `delete`해도 오류가 아니다(S3 동작과 같음).
- 클라이언트는 호출마다 `aioboto3.Session.client`로 연다. 앱 수명 동안 클라이언트를 유지하는 방식은 업로드 API(P6-3)에서 호출 빈도를 보고 정한다.

## 주요 결정
- **PR 분할 (사용자 결정):** P6을 P6-1(S3 어댑터) / P6-2(educator 모델) / P6-3(계약서 업로드·계약 API) / P6-4(수동 연결·멘토 프로필)로 나눈다.
- **타입 스텁 (사용자 결정, decisions B12):** mypy strict를 위해 `types-aioboto3[s3]`를 개발 의존성으로 추가하고 aioboto3 버전(15.5)에 맞춰 고정했다. 스텁이 요구하는 대로 클라이언트 설정은 `AioConfig`(s3v4, path-style)로 만든다.
- 테스트는 개발 버킷(`oz-backoffice-local`)이 아니라 테스트 전용 버킷을 만들어 쓴다. 개발 데이터와 섞이지 않게 하기 위해서다.

## 발견한 문제와 해결
- 처음에는 `types-aiobotocore[s3]`를 넣었다. 그런데 aioboto3 패키지 자체의 스텁이 없어 `import aioboto3`가 `import-untyped`로 실패했다. aioboto3 스텁을 포함하는 `types-aioboto3[s3]`로 바꿨다.
- `botocore.config.Config`는 스텁의 `Session.client` 오버로드와 맞지 않는다. `aiobotocore.config.AioConfig`로 바꿨다.

## 검증
- floci(인증 강제) 통합 테스트로 확인한 항목:
  - presigned POST: 정상 업로드 후 `head`로 크기·타입 확인. 크기 상한 초과, Content-Type 위반, 위조 서명은 거부된다.
  - presigned GET: 다운로드와 한글 파일 이름 헤더. 위조 서명과 만료(TTL 1초)는 거부된다. 서명 없는 GET은 403(비공개 버킷)이다.
  - `head`(없는 객체)와 `delete`
  - CORS preflight: 허용 origin은 응답하고, 비허용 origin은 거부된다.
  - 멀티파트 업로드와 Range GET(206)
- `docker compose exec api`에서 ruff, ruff format, mypy, mypy tests, lint-imports(10 kept), pytest 339 passed

## 남은 작업
- P6-2 educator 모델·마이그레이션, P6-3 계약서 업로드·계약 API, P6-4 수동 연결·멘토 프로필
- 운영 버킷 설정: 확정되지 않은 업로드 객체를 정리하는 수명 주기 규칙, CORS 허용 origin (배포 대상 확정 후)
