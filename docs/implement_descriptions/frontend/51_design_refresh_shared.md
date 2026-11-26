# 51. 디자인 다듬기 ① 공용 부품 (F92)

- 상태: PR 진행 중
- 관련 PR: #174
- 관련 결정: `docs/decisions.md` F91·F92 (F68)
- 이전 기록: [50. 멘토링 > 멘토링 설정 (FE-19a)](50_mentoring_settings.md)

## 배경
멘토링 설정에서 확정한 디자인(F91)을 앱 전체로 넓힌다(F92). 첫 PR은 공용 부품을 `components/`로 빼고, 모든 화면이 함께 쓰는 카드 표면·슬라이드 패널 모양을 한 번에 바꾼다. 화면별 구조 변경은 모듈별 PR에서 한다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `components/page-header.tsx` | `PageHeader`(제목 · 칩·상태 줄 · 설명 · 동작), `MetaChip` |
| `components/section-card.tsx` | `SectionCard`(아이콘 배지 + 제목·설명 + 동작, `rows`면 구분선 줄), `SettingRow` |
| `components/save-bar.tsx` | 떠오르는 저장 막대(상태 · [되돌리기] · [저장], 폼 밖이면 `form`) |
| `components/panel.tsx` | 패널 머리에 옅은 파스텔 그라데이션, 섹션은 둥근 카드 + 보라 띠 제목(회색 머리 없앰). 구성 규칙(F68)은 그대로 |
| 화면 전체 | 카드 표면 `rounded-xl border bg-card` → `rounded-2xl … shadow-sm` |
| `features/admin-mentoring` | 멘토링 설정이 공용 부품을 쓰게 정리 |

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(420개), `build`, `e2e`(50개, 화면 캡처로 패널·카드 확인)

## 남은 작업
- 모듈별 PR: 학사 → 강사·멘토·행정 → 회원 → 조직 → 설정·홈 → 수강생 → 멘토, 끝나면 Figma 반영.
