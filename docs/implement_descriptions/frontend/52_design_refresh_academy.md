# 52. 디자인 다듬기 ② 학사 (F92)

- 상태: PR 진행 중
- 관련 PR: #175
- 관련 결정: `docs/decisions.md` F91·F92
- 이전 기록: [51. 디자인 다듬기](51_design_refresh_shared.md)

## 배경
F92에 따라 F91 디자인 형식(페이지 머리 아이콘 타일·섹션 카드·설정 줄·요약 칸·상세 머리 카드, 둥근 2xl + 그림자)을 이 모듈 화면에 적용한다. 기능·API·주소는 바꾸지 않는다.

## 구현 내용
- PageHeader에 아이콘 타일(그라데이션) 추가
- 공용 ProfileHero(상세 머리 카드: 큰 아바타·이름·배지·한 줄 정보)·StatTile(아이콘 칩 요약 칸) 추가
- 수강생·과정·기수·HRD 과정 머리를 PageHeader로
- 수강생 상세: ProfileHero, 기본·수강 정보와 최근 신청·세션은 SectionCard, 멘토링 요약은 StatTile

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`, `build`, `e2e` (e2e 화면 캡처로 확인)

## 남은 작업
- 다음 모듈 디자인 다듬기, 끝나면 Figma 반영.
