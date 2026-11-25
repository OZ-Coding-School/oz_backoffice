# 42. 학사 > HRD 과정 (FE-17b)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #154
- 관련 결정: `docs/decisions.md` F75 (A20·A98)
- 이전 기록: [41. 학사 > 과정·기수 (FE-17a)](41_academy_bootcamps.md)

## 배경
학사 모듈의 두 번째 메뉴다. Airtable 동기화가 만드는 HRD-Net 훈련과정·회차(A20)를 보고, 동기화 값이 아닌 항목만 고친다. 선행 백엔드는 BE-3q HRD 연결 정보(#153, A98)이다.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-academy/api.ts` | HRD 과정 목록·회차 목록 조회, HRD 과정 저장(보낸 필드만, 빈 값은 null)·회차 자부담금 저장 |
| `features/admin-academy/labels.ts` | 훈련 유형·주말·주야간 문구, 금액·단위·기간 표시 |
| `features/admin-academy/components/hrd-page.tsx` | HRD 과정 표(이름·훈련과정 ID·훈련 유형·회차 수·연결 운영과정), 행 → 패널 |
| `features/admin-academy/components/hrd-sheet.tsx` | HRD 과정 패널: 기본 정보·훈련 정보(NCS 대·중·소, 주말·주야간, 훈련비·시간·일수)·연결 운영과정 목록·회차 목록(최근부터, 누르면 회차 패널). [수정]은 이름·훈련 정보(훈련과정 ID는 조회만) |
| `features/admin-academy/components/hrd-cohort-sheet.tsx` | 회차 패널: 회차·훈련 기간·연결 기수(조회만), 자부담금만 [수정] |
| `routes/_staff/admin/academy/hrd.tsx` | `/admin/academy/hrd?hrd=&cohort=` |
| `features/staff/nav.ts` | 학사 메뉴 'HRD 과정'(`academy.hrd.read`), 모듈 설명 '과정·기수 · HRD 과정' |
| `e2e/admin-academy.spec.ts` | HRD 과정 → 15회차 → 자부담금 저장 |

## 주요 결정 (사용자 결정, F75)
- HRD 과정 표 + 패널, 표 열은 이름·훈련과정 ID·훈련 유형·회차 수·연결 운영과정.
- 동기화 값(훈련과정 ID·회차 번호·기간) 외 항목만 수정, 추가·삭제 없음. 회차는 패널 목록 → 회차 패널에서 자부담금만.

## 발견한 문제와 해결
- 백엔드 응답의 기본값 필드(`bootcamps`·`cohort_count`·`linked_cohorts`)는 생성 타입에서 선택 필드라 화면에서 빈 배열로 다룬다.
- 수정 폼의 단위(원·시간·일) 너비가 달라 입력칸 끝이 어긋나 단위 칸 너비를 고정했다.

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul, 365개), `build`, `e2e`(46개)
- 개발 서버에서 1440 라이트·다크로 표·HRD 과정 패널(조회·수정)·회차 패널(조회·수정)을 확인(API는 모킹)

## 사용자 확인
- 화면을 확인하고 병합을 승인함.

## 남은 작업
- BE-3r 수강생 검색·상세 API → FE-17c 수강생.
