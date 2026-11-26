# 56. 디자인 다듬기 ⑥ 설정·운영진 홈 (F92)

- 상태: PR 진행 중
- 관련 PR: #179
- 관련 결정: `docs/decisions.md` F91·F92
- 이전 기록: [55. 디자인 다듬기](55_design_refresh_org.md)

## 배경
F92에 따라 F91 디자인 형식(페이지 머리 아이콘 타일·섹션 카드·설정 줄·요약 칸·상세 머리 카드, 둥근 2xl + 그림자)을 이 모듈 화면에 적용한다. 기능·API·주소는 바꾸지 않는다.

## 구현 내용
- 공휴일·운영진 홈 머리를 PageHeader(아이콘 타일)로

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`, `build`, `e2e` (e2e 화면 캡처로 확인)

## 남은 작업
- 다음 모듈 디자인 다듬기, 끝나면 Figma 반영.
