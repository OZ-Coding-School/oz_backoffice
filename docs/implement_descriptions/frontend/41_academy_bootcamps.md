# 41. 학사 > 과정·기수 (FE-17a)

- 상태: PR 진행 중
- 관련 PR: #152
- 관련 결정: `docs/decisions.md` F73·F74 (A20·A96·A97)
- 이전 기록: [40. 설정 > 공휴일 (FE-16)](40_settings_holidays.md)

## 배경
운영진 '학사' 모듈의 첫 화면이다. Airtable 동기화가 만드는 과정·기수(A20)를 보고 운영 항목만 고친다. 선행 백엔드는 BE-3o 기수 요약(#150, A96)과 BE-3p HRD 값(#151, A97)이다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-academy/api.ts` | 과정(사용 안 함 포함)·기수 목록·기수 단건·기수 요약·기수 멘토링 설정(없으면 null) 조회, 과정 저장(PATCH + 담당 팀 PUT, 바뀐 것만)·기수 저장 |
| `features/admin-academy/labels.ts` | 기수 상태 배지, 기간·HRD('AIG… · N회차')·운영시간 문구 |
| `features/admin-academy/components/bootcamps-page.tsx` | 왼쪽 과정 목록(사용 중 먼저, 사용 안 함 배지) · 오른쪽 과정 머리([과정 정보]) + 기수 표(최근 기수부터, 보관 기수 숨김) |
| `features/admin-academy/components/cohort-sheet.tsx` | 기수 패널: 기본 정보(조회만)·운영(상태·디스코드 서버, [수정])·수강생 상태별 인원·멘토·담당자·멘토링 설정(`mentoring.settings.read`일 때만, 없으면 '설정 전') |
| `features/admin-academy/components/bootcamp-sheet.tsx` | 과정 패널: 기본 정보(이름·코드·HRD 과정)·운영(사용 여부 스위치·기수 별칭·담당 팀). 담당 팀은 팀 조회 권한이 있을 때만 보이고 부서 관리 권한이 있을 때만 바꾼다 |
| `routes/_staff/admin/academy/bootcamps.tsx` | `/admin/academy/bootcamps?bootcamp=&cohort=&panel=bootcamp` |
| `features/staff/nav.ts` | 레일 '학사' 모듈, 메뉴 '과정·기수'(`academy.bootcamp.read`) |
| `e2e/admin-academy.spec.ts` | 레일 '학사' → 12기 패널 → 상태를 비활성으로 저장 |

## 주요 결정 (사용자 결정, F73·F74)
- 메뉴 과정·기수 / HRD 과정 / 수강생(명단 동기화 포함), 2단(과정 목록 · 기수 표), 운영 항목만 수정·추가·삭제 없음, 슬라이드 패널.
- 기수 패널에 수강생 상태별 인원·배정 멘토·담당자·멘토링 설정 요약.
- HRD는 내부 UUID 대신 훈련과정 ID·회차 번호(A97).

## 발견한 문제와 해결
- 'Airtable 기수 별칭' 라벨이 패널 라벨 칸(96px)에서 두 줄이 되어 '기수 별칭'으로 줄이고 설명은 `?`에 두었다.
- 기수 표의 HRD·디스코드 열이 잘려 열 너비를 고정값으로 맞췄다.
- 패널이 열려 있으면 뒤 화면이 접근성 트리에서 숨어 E2E에서 표를 찾지 못했다. 패널을 닫고 확인한다.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul, 360개), `build`, `e2e`(45개)
- 개발 서버에서 1440 라이트·다크로 목록·기수 패널(조회·수정)·과정 패널(조회·수정)을 확인(API는 모킹)

## 남은 작업
- FE-17b HRD 과정·회차.
