# 28. P6-3 계약서 업로드와 계약 관리 API

- 상태: PR 진행 중
- 관련 PR: #31
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P6 (P6-3)
- 이전 기록: [27. P6-2 멘토·강사·계약·계약서 모델](27_p6_2_educator_models.md), [26. P6-1 S3 어댑터](26_p6_1_s3_adapter.md)

## 배경
P6의 세 번째 PR이다. 운영진이 멘토·강사 계약을 등록하고, 계약서 PDF를 S3에 올리고, 계약 상태를 관리하는 기능을 만든다. 권한은 `contract.manage`다. 범위가 없는 권한이라 최고 관리자와 매니저 역할을 하나라도 가진 운영진이 쓸 수 있다(A16).

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `educator/domain/entities.py` | `EducatorContract`(정규화·검증, 상태 전이, 상태별 수정 가능 항목), `ContractFile`(`discard`) |
| `educator/domain/repositories.py`, `domain/uploads.py` | 리포지토리 Protocol, `ContractFilter`, 업로드 대기 정보·저장소 Protocol |
| `educator/application/contract_files.py` | `ContractFileUploadService`: 업로드 요청(파일 이름 검사, presigned POST)·확정(크기·타입·PDF 매직 바이트) |
| `educator/application/contracts.py` | `ContractService`: 목록·조회·생성·수정·확정·해지·삭제·계약서 URL·기간 만료 + 감사 로그 |
| `educator/infrastructure/repositories.py`, `pending_uploads.py` | Tortoise 리포지토리(필터·검색), Redis 업로드 대기 저장소(GETDEL) |
| `educator/presentation/admin_router.py` | 관리 API (아래 표) |
| `organization/application/employee_queries.py` | 다른 컨텍스트용 직원 존재 확인. `app.state.employee_queries`(B10) |
| `integrations/s3.py` | `read_prefix`(Range GET으로 앞부분 읽기) |
| `core/dependencies.py`, `main.py` | `get_file_storage`, `app.state.storage`(S3 어댑터) |
| `workers/tasks/contracts.py` | `educator.contracts.expire` 매일 00:05 KST (`cron_offset: Asia/Seoul`). compose 워커·스케줄러 명령에 모듈 추가 |
| `tests/s3_bucket.py`, `tests/conftest.py` | S3 테스트 버킷 픽스처(`s3_bucket`)를 공용으로 옮김. API 테스트도 floci 버킷을 쓴다 |

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/v1/admin/contract-files/uploads` | 업로드 요청 → `upload_id`, presigned POST(`url`, `fields`), 만료 시각, 최대 크기 |
| POST | `/api/v1/admin/contract-files/uploads/{upload_id}/confirm` | 확정 → 계약서 파일 |
| GET | `/api/v1/admin/contracts` | 목록 (`status` 여러 개, `educator_type`, `q`, `limit`/`offset`) |
| POST | `/api/v1/admin/contracts` | 생성 (항상 DRAFT, `contract_file_id` 선택) |
| GET / PATCH / DELETE | `/api/v1/admin/contracts/{id}` | 조회 / 수정(DRAFT, 확정 후 담당 직원만) / 삭제(DRAFT) |
| POST | `/api/v1/admin/contracts/{id}/confirm`, `/terminate` | 확정 / 해지 |
| GET | `/api/v1/admin/contracts/{id}/file-url` | 계약서 다운로드 presigned GET (원본 파일 이름으로 저장) |

- 상태 변경은 계획의 "PATCH"가 아니라 동작별 엔드포인트(`/confirm`, `/terminate`)로 나눴다. 수정과 상태 전이의 규칙이 달라서다.
- 감사 로그: `educator.contract_file.upload`, `educator.contract.{create,update,confirm,terminate,delete,expire}`. 기간 만료의 행위자는 시스템(NULL)이다.
- 계약서 교체·삭제 시 이전 파일은 `deleted_at`만 채운다. 버린 파일은 다른 계약에 다시 붙일 수 없다. 다른 계약이 쓰는 파일을 붙이면 409 `contract_file_in_use`.

## 주요 결정 (사용자 결정)
- **A24 상태 전이:**
  - DRAFT → ACTIVE: 계약서가 필요하다. 종료일이 이미 지났으면 바로 ENDED로 확정한다.
  - ACTIVE → TERMINATED: 수동으로 해지한다.
  - ACTIVE → ENDED: 매일 00:05 KST 작업이 자동 처리한다. 종료일 당일까지는 ACTIVE다.
- **A25 수정·삭제:**
  - 처음에는 상태와 무관하게 수정하는 안을 골랐다. 이후 "확정된 계약은 수정하면 안 된다"로 바꿨다. 그래서 DRAFT만 수정·삭제하고, 확정 후에는 담당 직원만 바꿀 수 있다.
  - 담당 직원은 항상 입력받는다.
  - 이전 계약서는 기록으로 보존한다(S3 객체도 남김).
  - 목록은 상태·유형 필터와 계약자 검색을 제공한다.
- **A26 업로드:**
  - 요청 정보는 Redis에 TTL로 두고, 요청자만 한 번 확정한다.
  - 확정 때 PDF 매직 바이트를 확인한다.
  - 파일 이름이 100자를 넘으면 요청을 거부한다.

## 발견한 문제와 해결
- 인프라(Redis 업로드 대기 저장소)가 응용 계층의 `PendingUpload`를 import해 계층 계약을 깼다. 대기 정보와 저장소 Protocol을 `domain/uploads.py`로 옮겼다.
- 확정 전에 업로드가 끝나지 않았으면(`head` 없음) 대기 정보를 다시 넣었다. 그래서 같은 업로드 ID로 다시 확정할 수 있다.
- 대기 키에 요청자 ID를 넣었다. 다른 사람이 확정을 시도해도 요청자의 대기 정보가 사라지지 않는다.

## 검증
- 단위: 도메인 규칙(정규화·검증, 상태 전이, 종료일 경계, 상태별 수정 항목), 파일 이름 검사, 업로드 확정(요청자만·한 번만, 업로드 전 재시도, PDF 아님·타입·크기 위반 시 객체 삭제), 계약 서비스(직원·파일 검증, 파일 교체 보존, 확정 후 규칙, 삭제, 기간 만료 멱등)
- 통합(PostgreSQL): 저장·조회 왕복, 필터·검색·정렬·페이지, 만료 대상 조회
- API(PostgreSQL + floci): 업로드 요청 → S3 직접 업로드 → 확정 → 계약 연결 → 확정 → 다운로드 URL로 받은 내용이 원본과 같음 → 해지. PDF가 아닌 내용은 422, 긴 파일 이름은 422, 목록 검색·DRAFT 삭제, 권한(비로그인 401, 조교 403, 매니저 200), 직원 없음 404, 기간 역전 422
- 커밋 6개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 400 passed다.
- 개발 환경: 워커·스케줄러가 `app.workers.tasks.contracts`를 불러온다. 만료 작업을 워커로 한 번 실행해 정상 종료를 확인했다(0건).

## 남은 작업
- P6-4 계약 수동 연결(멘토·강사)과 멘토 프로필 API
- 확정되지 않은 업로드 객체와 버린 계약서 객체 정리 정책 (운영 버킷 수명 주기 규칙, 배포 대상 확정 후)
