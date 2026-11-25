# 38. 조직 설정 > 직위와 패널 삭제 위치 (FE-15h)

- 상태: PR 진행 중
- 관련 PR: (PR 생성 후 기록)
- 관련 결정: `docs/decisions.md` F68(삭제 위치 변경)·F70 (A93)
- 이전 기록: [37. 조직 설정 > 부서와 영향 목록 (FE-15g)](37_org_departments.md)

## 배경
조직 설정의 마지막 메뉴인 직위다(F64). 직위의 담당 방식·데이터 범위·순서를 정한다(권한은 권한 메뉴). 시안 검토 때 "수정 → 삭제" 흐름이 어색하다는 의견으로 슬라이드 패널의 삭제를 조회 머리로 옮기기로 했고, 이미 만든 부서·팀 패널도 함께 바꾼다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `components/panel.tsx` | `PanelActions`: 조회 머리의 [수정] [삭제](빨간 테두리) |
| `features/admin-org/components/department-sheet.tsx`, `team-sheet.tsx` | 삭제를 수정 모드 아래에서 조회 머리로 옮김(삭제 확인 창은 패널이 연다) |
| `features/admin-org/text.ts` | 주격 조사(이/가) |
| `features/admin-positions/api.ts` | 직위 추가·수정·삭제, 순서 저장(바뀐 직위만 priority PATCH), 저장 뒤 직위·선택지·직원·조직·staff-access 다시 읽기 |
| `features/admin-positions/order.ts` | 우선순위 정렬, 옮기기, 바뀜 판단, 저장할 priority(자리마다 10 간격, 다른 값만), 새 직위 자리(맨 아래) |
| `features/admin-positions/components/positions-page.tsx` | 우선순위순 표, 손잡이 끌기(HTML 끌어 놓기)·키보드 ↑↓, '순서 바뀜' 배지, 아래 저장 영역 [되돌리기][순서 저장], 저장 안 한 순서로 떠나면 확인 |
| `features/admin-positions/components/position-sheet.tsx` | 패널: 기본 정보(`?` 설명)·직원(영향 조회)·권한(영역별 접는 상자, 읽기만). 수정·추가, 담당 방식·데이터 범위 변경 확인 창(바뀐 항목 + 영향받는 대상), 삭제(남은 직원·신청이 있으면 목록과 [닫기]만) |
| `routes/_staff/admin/org/positions.tsx`, `features/staff/nav.ts` | `/admin/org/positions?position=`, 조직 설정 두 번째 메뉴 '직위'(`org.position.read`) |
| `e2e/admin-positions.spec.ts` | 끌어서 순서 바꾸기 → 저장 |

- 직원 목록은 직위 관리·권한 관리 권한이 있을 때만(영향 조회 권한), 권한 내용은 권한 조회 권한이 있을 때만 보인다. 없으면 수·안내만.
- Figma: `Icon/grip-vertical` 추가, 부서·팀·직위 패널 머리에 [삭제].

## 주요 결정 (사용자 결정, F68·F70)
- 표 목록 + 슬라이드 패널, 순서는 끌어서 바꾸고 [순서 저장].
- 패널에 기본 정보·직원·권한 요약.
- 담당 방식·데이터 범위 변경과 삭제는 부서와 같은 방식(영향 목록, 막히면 [닫기]만).
- 슬라이드 패널의 삭제는 조회 머리의 [수정] 옆, 수정 모드에는 넣지 않는다(부서·팀 패널도 같이 바꿈).

## 발견한 문제와 해결
- 없음

## 검증
- `lint`, `format:check`, `typecheck` 통과
- `vitest` 337 passed (UTC·Asia/Seoul). 새 테스트: 순서 계산·조사, 표 순서·키보드 이동·되돌리기·순서 저장 본문, 패널 섹션·권한 접힘·[수정][삭제], 담당 방식 변경 확인 창·저장 본문, 삭제 불가, 직위 추가(맨 아래·이름 중복), 조회 권한만. 부서·팀 테스트는 머리의 [삭제]로 바꿈
- `build`, Playwright E2E 42 passed (실제 끌어 놓기 포함)
- 1440 라이트·다크 화면 확인(순서 바꿈, 패널, 수정, 변경 확인, 삭제 불가)

## 남은 작업
- BE-3m 전체 회원 API, 15i 전체 회원
