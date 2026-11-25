# 94. 법정공휴일 동기화 (BE-3n)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #148
- 관련 결정: `docs/decisions.md` A95, B16 (B15 변경)
- 이전 기록: [93. 전체 회원 API (BE-3m)](93_member_users.md)

## 배경
FE-16 공휴일 화면을 그리면서 `holidays` 패키지(오프라인 계산, B15)를 확인했다. 대체공휴일·선거일과 배포 시점에 알려진 임시공휴일은 들어 있지만, 새로 발표된 임시공휴일은 패키지를 올려야만 반영된다. 사용자가 공공데이터포털 특일 정보 API로 바꾸기로 했다(A95·B16).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `mentoring/domain/settings.py`, `domain/repositories.py` | `PublicHoliday`, `PublicHolidaySync`, `PublicHolidayRepository`(기간 조회·그해 통째 교체·동기화 기록) |
| `mentoring/infrastructure/models/settings.py`, 마이그레이션 33 | `public_holidays`(날짜·이름 유니크, 날짜 인덱스), `public_holiday_syncs`(연도 기본키, 시각·건수) |
| `mentoring/infrastructure/repositories.py` | `TortoisePublicHolidayRepository` (교체는 삭제 + `bulk_create` + 동기화 기록 upsert) |
| `mentoring/application/calendar.py` | `BusinessCalendar(추가 휴일, 법정공휴일 저장소)`: 패키지 대신 DB를 읽는다. 받지 않은 해는 법정공휴일 없음 |
| `mentoring/application/holiday_sync.py` | `PublicHolidaySyncService`: 올해·내년(KST)을 모두 받은 뒤 한 트랜잭션에서 그해를 교체(중복·다른 해 날짜 제거, 0건이면 비움). 호출이 실패하면 아무 해도 바꾸지 않는다 |
| `integrations/data_go_kr/holidays.py` | 특일 정보 `getRestDeInfo` 어댑터(httpx, `isHoliday=Y`만, 항목 하나·없음 형식 처리, XML 오류·HTTP 오류 → 503 `holiday_sync_failed`), 개발·테스트용 2025~2027 고정 자료 |
| `core/holidays.py`, `core/config.py`, `.env.example` | `HOLIDAY_DRIVER`(`fixed`·`data_go_kr`)·`HOLIDAY_API_KEY`로 출처 선택(키 없으면 None) |
| `mentoring/presentation/settings_router.py` | `GET /admin/mentoring-holidays?year=` → `{items, synced_at}`, `POST /admin/mentoring-holidays/sync`(추가 휴일 등록과 같은 권한, 결과 연도별 건수·시각) |
| `workers/tasks/mentoring.py` | `mentoring.public_holidays.sync` 매일 03:00 KST(`cron_offset`), 실패하면 로그만 남기고 유지 |
| `availability_router.py`, 워커 신청 서비스 조립 | 새 `BusinessCalendar` 인자 |
| `pyproject.toml`, `uv.lock` | `holidays` 패키지 제거 |
| `docs/database_schema_v2.dbml`, `docs/operations/*` | 두 테이블, 환경 변수·첫 배포 순서·정기 작업, 서비스 키 신청 방법(외부 준비물 8) |
| `apps/frontend` | `openapi.json`·`schema.gen.ts` 다시 생성 |

## 주요 결정 (사용자 결정, A95·B16)
- DB 저장 + 매일 03:00 KST 올해·내년 동기화, 받지 못한 해는 공휴일 없음(대체 계산 없음).
- 응답 그대로 반영(0건이면 그해를 비움), 화면의 [지금 가져오기]는 올해·내년.
- 조회 응답은 `{items, synced_at}` 객체로 바꿈(프론트에서 아직 쓰는 곳 없음).
- PR은 백엔드 먼저, 화면은 FE-16.

## 발견한 문제와 해결
- aerich가 `SmallIntField(primary_key=True)`를 `SMALLSERIAL`로 만들었다. 연도는 직접 넣는 값이라 `generated=False`로 고치고 마이그레이션을 `SMALLINT`로 고쳤다. `created_at` 기본값 `now()`는 raw SQL로 넣었다.
- API 테스트는 lifespan을 돌리지 않아 공유 HTTP 클라이언트(`app.state.http_client`)가 없다. 동기화 테스트에만 픽스처로 둔다.

## 검증
- `ruff check`, `ruff format --check`, `mypy`, `mypy tests`, `lint-imports`, `pytest`(통합 포함): 910 passed
- 마이그레이션: 개발 DB에서 upgrade → migrate("No changes detected") → downgrade -v 33 → upgrade
- DBML 파서(`@dbml/core`, dbmlv2) 통과
- 실제 특일 정보 API 호출은 서비스 키가 없어 확인하지 못했다(respx로 형식만 검증).

## 남은 작업
- 서비스 키를 받으면 `HOLIDAY_DRIVER=data_go_kr`로 실제 호출을 확인한다.
- FE-16 공휴일 화면(조회·추가·삭제·[지금 가져오기]).
