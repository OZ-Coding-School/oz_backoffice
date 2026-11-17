# 58. refresh 재사용 유예 시간

- 상태: 완료 (2026-11-17 병합)
- 관련 PR: #73
- 관련 결정: `docs/decisions.md` A60 (A7 보완), F19
- 이전 기록: [57. 운영진 멘티 목록·신청·세션 수 집계](57_mentee_list.md)

## 배경
프론트엔드 API 클라이언트(FE-0b)를 설계하다가 문제를 발견했다. refresh 토큰은 갱신할 때마다 회전하고, 이미 쓴 토큰이 다시 오면 탈취로 보고 그 사용자의 세션을 모두 끊는다(A7). 그런데 쿠키를 공유하는 탭 여러 개가 거의 동시에 갱신하면 둘 다 같은 refresh를 보낸다. 그러면 늦게 도착한 요청이 재사용으로 판정돼 **정상 사용자가 전체 로그아웃**된다. 브라우저를 다시 열어 탭 여러 개가 함께 시작될 때나 네트워크 재전송 때도 같은 일이 생긴다.

사용자는 두 가지를 함께 적용하기로 했다(A60·F19).
- 백엔드: 회전 직후 짧은 유예 시간
- 프론트: 탭 간 잠금으로 갱신을 한 번에 하나씩

이 PR은 백엔드 쪽이다.

## 구현 내용

| 파일 | 바꾼 것 |
| --- | --- |
| `identity/domain/sessions.py` | `RefreshLookup`에 사용 시각·회전 여부·사용자 마지막 폐기 시각을 추가했다. 저장소 메서드는 `now`를 받는다. |
| `identity/infrastructure/token_store.py` | 아래 "저장 형식" 참고 |
| `identity/application/tokens.py` | `consume_refresh`가 `ConsumedRefresh(user_id, rotated)`를 돌려준다. 유예를 판정하고, `issue_access()`(access만 발급)를 추가했다. |
| `identity/application/auth_service.py` | `SessionService.refresh`는 회전이면 `IssuedTokens`, 유예면 `IssuedAccess`를 돌려준다. |
| `identity/presentation/router.py` | `/auth/refresh`가 유예면 access만 응답하고 **refresh 쿠키를 설정하지 않는다**(`Cache-Control: no-store`는 같다). |
| `core/config.py`, `.env.example`, `docs/operations/production_notes.md` | `REFRESH_REUSE_GRACE_SECONDS`(기본 10) |

**저장 형식** (`token_store.py`)
- 쓰인 토큰 기록 `refresh-used:<jti>`에 `user_id|사용 시각|R(회전)/V(폐기)`를 저장한다.
- 로그아웃·전체 폐기 때는 사용자별 `refresh-revoked-at:<user_id>`에 시각을 남긴다.

**판정 규칙** (`TokenService`)

| 경우 | 결과 |
| --- | --- |
| 활성 토큰 | 회전한다. 새 access와 새 refresh |
| 회전으로 쓰인 지 10초 이내이고, 그 뒤 로그아웃·전체 폐기가 없음 | 유예. 새 access만, 쿠키는 그대로 |
| 10초가 지난 재사용, 로그아웃된 토큰의 재사용, 폐기 뒤의 재사용 | 지금처럼 탈취로 보고 전체 폐기 + 401 `refresh_token_reused` |
| 모르는 토큰 | 401 `refresh_token_revoked` (변화 없음) |

## 주요 결정 (사용자 결정, A60)
- 회전과 재사용 탐지는 유지하고 **유예 시간 10초**를 둔다(설정 가능).
- 유예 안의 재사용에는 **access만 주고 쿠키는 바꾸지 않는다**. 먼저 온 응답이 준 새 refresh가 브라우저에 남으므로 refresh가 한 줄로 유지된다.
- 프론트는 Web Locks로 탭 간 갱신을 직렬화한다(F19, FE-0b에서 구현).

## 구현 세부
- **유예 판정은 Redis TTL이 아니라 기록한 사용 시각과 `Clock`으로 한다.** 테스트에서 시각을 고정해 경계값(정확히 10초 / 10초 초과)을 확인할 수 있다.
- **유예는 회전으로 쓰인 토큰에만 준다.** 로그아웃으로 폐기된 토큰(`V`)은 바로 재사용으로 본다.
- **로그아웃·전체 폐기는 그 사용자의 유예를 끝낸다.** 마지막 폐기 시각이 사용 시각보다 뒤면 유예하지 않는다. 그래서 탈취 탐지·계정 정지 뒤에 남은 유예로 access를 받을 수 없다.
- **사용 시각을 기록하기 전 형식**(값이 `user_id`뿐)의 기록은 유예 없이 재사용으로 본다(배포 전후 호환).
- **시각은 ISO 8601 문자열로 저장한다.** 처음에 epoch 초를 소수 3자리로 저장했더니, 반올림 때문에 정확히 10초인 경계가 10초를 넘는 것으로 계산됐다.

## 검증
- **단위 테스트** (`test_tokens.py`)
  - 유예 안 재사용은 access만(경계 10초 포함)이고, 다른 세션은 그대로다.
  - 유예가 지난 재사용은 전체 폐기다(기존 테스트에 시각 이동 추가).
  - 로그아웃 뒤, 전체 폐기 뒤, 로그아웃된 토큰에는 유예가 없다.
  - 이전 형식 기록도 재사용으로 본다.
- **서비스 테스트** (`test_auth_service.py`): 유예면 `IssuedAccess`를 돌려준다.
- **API 테스트** (`test_auth.py`)
  - 유예 안 재사용은 200으로 access만 주고 Set-Cookie가 없으며, 먼저 받은 새 refresh는 그대로 쓸 수 있다.
  - 11초 뒤 재사용은 401 `refresh_token_reused`이고, 새 refresh도 폐기된다.
- **로컬 검사 (compose `api` 컨테이너):** ruff, ruff format, mypy, mypy tests, lint-imports 통과. 전체 837 passed.

- GitHub Actions (PR #73): 백엔드 검사 잡 통과
- 사용자가 병합을 확인했다(2026-11-17)

## 남은 작업
- FE-0b: 프론트 API 클라이언트에서 Web Locks로 갱신을 직렬화한다(F19).
