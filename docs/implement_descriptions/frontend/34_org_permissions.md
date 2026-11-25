# 34. 조직 설정 > 권한 (FE-15d)

- 상태: PR 진행 중
- 관련 PR: #137
- 관련 결정: `docs/decisions.md` F63·F64·F65 (A86·A87)
- 이전 기록: [33. 직원·담당자 (FE-15c)](33_staff_and_employees.md)

## 배경
권한 모델을 엔터티 × 조회/관리(A86)와 직위 = 역할(A87)로 바꾼 뒤, 직위별 권한을 정하는 화면이 필요하다. 메뉴는 새 '조직 설정' 모듈(F64)에 두고, 이번 PR은 권한 메뉴만 만든다(F65).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-permissions/api.ts` | 직위 목록(`GET /admin/positions`), 권한 정의(`GET /admin/permissions`), 권한 저장(`PUT /admin/positions/{id}/permissions`, 저장 뒤 직위 캐시를 응답으로 고치고 staff-access를 다시 읽음) |
| `features/admin-permissions/groups.ts` | 권한 정의 → 영역별 엔터티 행([조회][관리·동작]), 관리를 켜면 조회도·조회를 끄면 관리도(A86), 변경 비교, 저장 본문 순서, 직위 설명 문구 |
| `features/admin-permissions/components/permissions-page.tsx` | 왼쪽 직위 목록(고르기만), 오른쪽 직위 머리·그룹 접기/펼치기·모두 펼치기/접기·엔터티 행, 하단 저장 영역(변경이 있을 때만 [변경 취소][저장] → 확인 창), 저장 안 한 변경 확인 창(`useBlocker`), 좌우 각각 스크롤 |
| `routes/_staff/admin/org/permissions.tsx` | `/admin/org/permissions?position=` (없으면 첫 직위), 직위·정의 미리 불러오기 |
| `features/staff/nav.ts` | 조직 설정 모듈(레일 '조직')과 권한 메뉴(`access.role.read`) |
| `e2e/admin-permissions.spec.ts` | 관리를 켜고 확인 후 저장 |

- 바꿀 권한(`access.role.manage`)이 없으면 체크박스가 비활성이고 저장 영역 대신 '볼 수만 있어요' 안내가 보인다.
- 직위 추가·수정·삭제는 다음 '직위' 메뉴에서 한다(이 화면은 고르기만).

## 주요 결정 (사용자 결정, F63·F64·F65)
- 왼쪽 직위 목록·오른쪽 권한, 그룹 접기·펼치기, 좌우 각각 스크롤, 하단 sticky 저장 영역(변경이 있을 때만 버튼), 조직 설정 모듈·`/admin/org/...`, 이번 PR은 권한 메뉴만.

## 발견한 문제와 해결
- 스크롤 영역 안의 그룹 상자가 flex 축소로 눌려 잘렸다 → 그룹·안내에 `shrink-0`.

## 검증
- `lint`, `format:check`, `typecheck` 통과
- `vitest` 313 passed (UTC·Asia/Seoul). 새 테스트: 그룹·토글·비교 단위, 직위 고르기·그룹 접기, 관리→조회 자동·조회 끄면 동기화 꺼짐·확인 후 저장 본문, 변경 취소·저장 오류, 저장 안 한 채 직위 바꾸기 확인, 조회만 있을 때 비활성, 레일·메뉴
- `build`, Playwright E2E 40 passed
- 1440 라이트·다크, 실제 권한 정의 40개로 화면 확인(Figma 시안과 비교)

## 남은 작업
- 메뉴 개편(회원 관리·가입 승인 통합·직원 이동), 부서·직위·직원 메뉴(F64)
