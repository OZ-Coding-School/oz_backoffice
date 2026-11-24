# 27. FE-12a 멘토 정산 목록·명세

- 상태: 완료 (2026-11-24 병합)
- 관련 PR: #120
- 관련 결정: `docs/decisions.md` F55 (F54·A55·A56·A78·A80·F36)
- 이전 기록: [26. FE-11b 멘토 불가 시간 추가·수정·삭제·충돌 확인](26_mentor_unavailable_edit.md)

## 배경
FE-12의 두 번째 PR이다(F54). 멘토가 운영진이 마감한 정산과 정산서 명세를 본다. 앞선 BE-2n(#119, A80)이 정산 응답에 기수 이름과 명세 항목의 상대·주제를 더했다.

시안은 데스크톱만 있었다(`Screen / 정산 목록`·`정산 상세`). 구현 전에 Figma에 그렸다(F49 배치).
- 각 크기 Section: `정산 · 목록·상세 (FE-12a)`. 데스크톱은 기존 시안에 FE-2 사이드바·기수 필터를 붙였고, 태블릿·휴대폰은 카드다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/mentor-settlements/api.ts` | `mySettlementsQuery`(`GET /me/mentor-settlements`), `mySettlementQuery(id)` |
| `features/mentor-settlements/labels.ts` | `summaryCards`(가장 최근 달·그 전 달·올해 KST 누적), `won`, `monthTitle`, `closedLabel`, `unitPrice`(시간·회·월·일괄), `detailSubtitle`, `counterpartLabel`, `itemTypeLabel` |
| `features/mentor-settlements/components/settlements-page.tsx` | 목록: 제목·기수 필터, 요약 3칸, lg 표 / 그 밖 카드, 빈 상태(전체·기수) |
| `features/mentor-settlements/components/settlement-page.tsx` | 명세: 뒤로 가기, 머리(월·기수, 기준·단가·마감, 마감 배지), 합계 3칸, lg 표 / 그 밖 카드, 404 안내 |
| `routes/_member/mentor/settlements/index.tsx`, `$settlementId.tsx` | `?cohort=`, 멘토만(`requireAccount`), 목록·배정 미리 불러오기 |
| `features/member/nav.ts`, `components/member-shell.tsx` | 멘토 메뉴 '정산'(채팅 다음). 하단 탭 고정 메뉴를 계정별로(`pinnedTabs`): 멘토는 홈·받은 신청·세션·채팅 |

- 기수 필터는 `CohortSelect`(배정 기수)를 다시 쓰고, 목록 API에 기수 조건이 없어 화면에서 거른다. 요약 3칸도 거른 목록으로 계산한다.
- 그 전 달은 가장 최근 달의 바로 전 달력 달이다(1월이면 지난해 12월). 정산이 없으면 0원 · '정산 없음'이다.
- 미차감 초과(`uncharged_overtime_minutes`, A78)는 보여 주지 않는다(F54).

## 주요 결정 (사용자 결정)
- F54: 주소 `/mentor/settlements`·`/mentor/settlements/{id}`, 메뉴는 채팅 다음, 요약 3칸, 미차감 초과 숨김.
- F55: 시안 확인, 휴대폰 하단 탭에서 멘토는 채팅을 고정한다(일정·정산은 더보기).

## 검증
- `lint`, `typecheck`, `format:check`, `build` 통과
- `vitest` 263 passed (TZ=UTC·America/Los_Angeles·Asia/Seoul). 새 테스트: 요약 계산·표시 함수, 목록·기수 필터·빈 상태, 명세(미차감 초과 숨김)·404, 멘토 하단 탭
- `playwright` 32 passed. 새 E2E: 데스크톱 메뉴 → 정산 → 명세, 휴대폰 더보기 → 정산 → 카드. 멘토 일정 E2E는 더보기에서 들어가도록 고쳤다
- 390·768·1440 화면을 시안과 비교했다

- GitHub Actions (PR #120): 프론트엔드 검사·E2E 3개 통과
- 사용자가 병합을 확인했다(2026-11-24)

## 남은 작업
- FE-12b 내 프로필(`/my/profile`의 멘토 프로필 편집, 사진, 배정 기수)
