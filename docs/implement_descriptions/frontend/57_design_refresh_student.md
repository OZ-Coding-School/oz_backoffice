# 57. 디자인 다듬기 ⑦ 수강생 화면 (F92)

- 상태: PR 진행 중
- 관련 PR: #180
- 관련 결정: `docs/decisions.md` F91·F92
- 이전 기록: [56. 디자인 다듬기](56_design_refresh_settings.md)

## 배경
F92에 따라 F91 디자인 형식(페이지 머리 아이콘 타일·섹션 카드·설정 줄·요약 칸·상세 머리 카드, 둥근 2xl + 그림자)을 이 모듈 화면에 적용한다. 기능·API·주소는 바꾸지 않는다.

## 구현 내용
- 홈·신청 내역·신청 변경·진행 기록·시간 지급·차감 내역 머리를 PageHeader로(아이콘 타일은 태블릿 이상)
- 홈 요약 칸 아이콘을 칩으로(멘토 홈도 같은 부품)
- 홈 '멘토링' 카드 제목을 CardTitle로
- PageHeader는 앱 상단 막대와 겹치지 않게 header 대신 div

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`, `build`, `e2e` (e2e 화면 캡처로 확인)

## 남은 작업
- 다음 모듈 디자인 다듬기, 끝나면 Figma 반영.
