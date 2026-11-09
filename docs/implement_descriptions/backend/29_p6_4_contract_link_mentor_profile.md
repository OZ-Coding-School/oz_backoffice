# 29. P6-4 계약 수동 연결과 멘토 프로필 API

- 상태: PR 진행 중
- 관련 PR: #32
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P6 (P6-4)
- 이전 기록: [28. P6-3 계약서 업로드와 계약 관리 API](28_p6_3_contract_api.md)

## 배경
P6의 마지막 PR이다. 운영진이 계약을 가입한 멘토·강사 프로필에 직접 연결할 수 있게 한다. 자동 매칭(P7)이 실패한 경우를 위한 기능이다. 멘토 소개 정보(프로필·사진)를 멘토 본인과 운영진이 관리하는 API도 만든다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `educator/application/uploads.py` | `DirectUploads`: 직접 업로드 발급·수령(대기 정보, 크기·타입·매직 바이트 검사)을 계약서와 사진이 함께 쓴다. `UploadSpec`은 용도·허용 타입·상한·형식 검사를 정의한다 |
| `educator/domain/uploads.py`, `infrastructure/pending_uploads.py` | 대기 정보에 용도(`purpose`)를 넣고 키에 포함. 다른 용도의 업로드 ID로는 확정할 수 없다 |
| `educator/domain/entities.py` | `EducatorContract.link`(유형-프로필 종류 일치, 상태 무관, 둘 다 None이면 해제) |
| `educator/domain/profiles.py` | `Mentor` 엔티티: 텍스트 정규화·길이(닉네임 30, 한 줄 소개 100, 전문 분야 200, 소개 10,000), NICKNAME 표시는 닉네임 필요, `replace_image` |
| `educator/application/contracts.py` | `ContractService.link` (프로필 존재 확인, 감사 로그 `link`/`unlink`) |
| `educator/application/mentor_profiles.py` | `MentorProfileService`: 조회·목록(계약 수)·수정·사진 업로드 확정·삭제. 이전 사진은 커밋 후 S3에서 지운다 |
| `educator/infrastructure/repositories.py` | 멘토 리포지토리(회원 이름·이메일·휴대폰·닉네임 검색, FK 조인), 강사 존재 확인, 멘토별 계약 수 |
| `educator/presentation/admin_router.py`, `mentor_router.py` | 연결 API, 멘토 본인·운영진 프로필 API |
| `tests/factories/educator.py` | 가입 기능 전이라 멘토·강사 프로필을 직접 만드는 빌더 |

| 메서드 | 경로 | 권한 |
| --- | --- | --- |
| POST / DELETE | `/api/v1/admin/contracts/{id}/link` | contract.manage (`mentor_id` 또는 `instructor_id` 하나 / 해제) |
| GET / PATCH | `/api/v1/me/mentor-profile` | 승인된 회원 + 멘토 프로필 |
| POST | `/api/v1/me/mentor-profile/image/uploads`, `…/{upload_id}/confirm` | 같음 |
| DELETE | `/api/v1/me/mentor-profile/image` | 같음 |
| GET | `/api/v1/admin/mentors` | contract.manage (`q`, `is_active`, `limit`/`offset`, 계약 수) |
| GET / PATCH | `/api/v1/admin/mentors/{id}/profile` | contract.manage |
| POST / DELETE | `/api/v1/admin/mentors/{id}/profile/image/uploads`(·`/{upload_id}/confirm`), `…/profile/image` | contract.manage |

- 응답의 `display_name`은 표시 이름 선택을 반영한다(NICKNAME이면 닉네임, 아니면 실명). `profile_image_url`은 조회할 때마다 presigned GET(10분)을 발급한다.
- 사진 업로드의 용도에는 멘토 ID가 들어간다(`mentor_image:<ID>`). 다른 멘토의 업로드 ID로는 확정할 수 없다.

## 주요 결정 (사용자 결정)
- **A27 수동 연결:** 이미 있는 프로필만 지정한다. 프로필 생성·역할 부여는 P7에서 한다. 계약 상태와 무관하게 연결·변경·해제할 수 있다.
- **A28 멘토 프로필:**
  - 사진 최적화: 처음에는 서버에서 최적화하는 안을 검토했다(새 의존성 Pillow 필요). 최종적으로 **브라우저가 최적화**하고 서버는 형식만 검사하기로 했다. 서버 의존성은 늘지 않는다.
  - 사진 교체·삭제: 이전 사진 객체를 지운다.
  - 프로필 API: 본인 수정과 운영진 대리 수정을 둘 다 둔다. 운영진용 목록은 멘토만 둔다. 소개는 10,000자까지다.
  - 활성 여부 변경은 P8에서 정한다.

## 발견한 문제와 해결
- 계약서 업로드(P6-3)와 사진 업로드가 같은 흐름이다. 먼저 `refactor:` 커밋으로 공통 흐름을 `DirectUploads`로 옮겼다(동작 변경 없음, 400 passed 유지). 이후 허용 Content-Type을 여러 개 받도록 `UploadSpec`을 넓혔다.
- 업로드 대기 정보에 용도가 없으면 계약서 업로드 ID로 사진을 확정할 수 있다. 용도를 키에 넣어 막았다.

## 검증
- 단위:
  - 프로필 규칙: 정규화, 경계 길이, 닉네임 표시, 사진 키 교체
  - 이미지 시그니처: 타입과 내용이 다르면 거부
  - 계약 연결: 끝난 계약 연결·변경·해제, 유형 불일치, 없는 프로필
  - 프로필 서비스:
    - 감사 로그
    - 사진 교체 시 이전 객체 삭제
    - 형식·크기 위반 시 객체 삭제
    - 다른 멘토 업로드 ID 거부
- 통합(PostgreSQL): 멘토 검색(이름·이메일 대소문자·휴대폰·닉네임), 활성 필터, 저장 왕복, 멘토별 계약 수, 강사 존재 확인
- API(PostgreSQL + floci):
  - 멘토 본인: 프로필 조회·수정(표시 이름), 닉네임 필수 규칙, 사진 업로드 → presigned GET으로 받은 내용이 원본과 같음, 사진 삭제
  - 접근 제한: 멘토가 아닌 회원은 404, 승인 대기 회원은 403
  - 운영진: 목록 검색·계약 수, 대리 수정·사진 업로드, 권한(401·403)
  - 계약 연결·해제: 유형 불일치, 둘 다 보내면 422
- 커밋 3개를 worktree에서 하나씩 검사했다(ruff, ruff format, mypy, mypy tests, lint-imports, pytest). 모두 통과했고 최종 431 passed다.

## 남은 작업
- P7 수강생·멘토 가입: 멘토 자동 매칭으로 프로필 생성·계약 연결·역할 부여, 승인 흐름에서 계약 선택
- P8에서 멘토 활성 여부 변경과 그 영향 결정
- 운영 버킷 수명 주기 규칙(확정되지 않은 업로드 정리)
