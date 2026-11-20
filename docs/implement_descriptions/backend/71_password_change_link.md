# 71. 내 정보 비밀번호 변경 링크 (BE-2f)

- 상태: 완료
- 관련 PR: #98
- 관련 결정: `docs/decisions.md` A72, F36 (A32)
- 이전 기록: [70. 녹화 끝 시각 (BE-2e)](70_artifact_recording_end.md)

## 배경
FE-6a 내 정보의 [비밀번호 재설정]은 코드 입력 방식(A32) 대신, 메일로 받은 인증 링크를 누르면 열려 있던 내 정보 화면에서 새 비밀번호 입력이 활성화되는 방식으로 정했다(A72, 사용자 결정). 로그인 화면의 '비밀번호 찾기'는 코드 방식을 그대로 둔다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `identity/domain/password_change.py` | 링크 상태(보냄·인증·없음), 30분·10분·1분·하루 5회 |
| `identity/infrastructure/password_change_store.py` | Redis 저장소. 회원별 링크 상태와 토큰 해시 → 회원 ID. 토큰 원문은 저장하지 않는다 |
| `identity/application/password_change.py` | 상태 조회, 링크 보내기(전 링크 무효, 발송 실패 시 지움), 링크 확인(한 번만), 변경(감사 로그, 로그인 잠금 해제, 세션 유지) |
| `identity/presentation/password_change_router.py`, `api/v1.py` | API 네 개 |
| `apps/frontend/openapi.json`, `src/api/schema.gen.ts` | 다시 만들었다(F19) |

### API

| API | 내용 |
| --- | --- |
| `GET /me/password-change` | `available`(비밀번호 계정인지), `state`(NONE·SENT·VERIFIED), `expires_at` |
| `POST /me/password-change/link` | 내 이메일로 링크. 1분 안 다시 보내면 429 `resend_too_soon`, 하루 5회를 넘으면 429 `rate_limited`, Google 전용 계정은 `password_not_available` |
| `POST /auth/password-change/verify` | 로그인 없이 링크 토큰 확인(204). 만료·사용됨·모름은 `password_link_invalid` |
| `POST /me/password-change` | 인증된 10분 안에 새 비밀번호(204). 아니면 `password_change_not_verified`, 규칙은 가입과 같다 |

링크 주소는 `FRONTEND_BASE_URL` + `/password-change/verify?token=…`이다(화면은 FE-6a).

## 주요 결정 (사용자 결정, A72)
- 링크 30분·한 번만, 인증 후 10분 안에 저장, 다시 보내기 1분 간격·하루 5회, 새 링크를 보내면 전 링크 무효
- 비밀번호 규칙은 가입과 같고, 바꾼 뒤 세션 유지·로그인 잠금 해제(A32와 같음)
- 내 정보 화면이 5초마다 상태를 확인하고, Google 전용 계정에는 버튼을 숨긴다

## 발견한 문제와 해결
- 없음

## 검증
- 단위: 링크 → 인증 → 변경 흐름, 30분·10분 경계, 전 링크 무효·1분 간격·하루 5회, Google 전용 계정, 비밀번호 규칙, 발송 실패 시 링크 없음, 모르는 토큰
- API: 상태 → 링크 → 인증 전 변경 거부 → 링크 확인(두 번째는 거부) → 변경 → 새 비밀번호로 로그인, 세션 유지, 비로그인 401
- **로컬 검사 (compose `api`):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 896 passed.
- **프론트엔드:** 다시 만든 타입으로 `typecheck` 통과
- **CI:** 통과. 사용자가 병합을 확인했다(2026-11-20)

## 남은 작업
- FE-6a 내 정보 화면과 링크 인증 화면
- 실제 Gmail 발송으로 링크 메일 확인
