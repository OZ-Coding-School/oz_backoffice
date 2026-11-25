# 46. 행정 업무 > 계약, 멘토 계약 탭·가입 전 멘토 (FE-18b)

- 상태: 완료 (2026-11-25 병합)
- 관련 PR: #166
- 관련 결정: `docs/decisions.md` F83 (F81·F82 변경, A23~A27·A103~A105)
- 이전 기록: [45. 강사·멘토 > 멘토 (FE-18a)](45_admin_mentors.md)

## 배경
멘토·강사 계약을 운영진이 등록·확정·해지하고 계약서를 관리한다. 시안을 세 번 거쳐(계약 메뉴 → 멘토 상세 안 → 행정 업무) 레일 '행정 업무' 모듈의 '계약' 메뉴로 정했다(F83). 멘토 계약은 항상 멘토에 속하고 가입 전이면 가입 전 멘토가 생긴다(A104·A105).

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/admin-contracts/api.ts` | 목록(상태·유형·검색·멘토, 20개씩), 단건, 담당 직원 후보, 계약서 업로드(요청 → S3 → 확정)·보기 주소, 추가·수정·확정·해지·삭제·옮기기 |
| `features/admin-contracts/labels.ts` | 상태 배지, 유형, 기간, 연결 표시(이름(닉네임)·미연결), 파일 크기, 오류 문구 |
| `features/admin-contracts/components/contracts-page.tsx` | `/admin/administration/contracts?status=&type=&q=&contract=`: 상태·유형·검색 + 표(계약자·유형·제목·기간·연결·담당·상태) + [계약 추가] |
| `features/admin-contracts/components/contract-sheet.tsx` | 패널: 계약 정보·계약서 [보기]·멘토 [멘토 보기]·[다른 멘토로 옮기기]·담당 직원 [변경]. 작성 중 [삭제]·[수정]·[확정], 진행 중 [해지](확인 창) |
| `features/admin-contracts/components/contract-form.tsx` | 추가·수정 폼(유형은 추가 때만, 계약서 PDF는 고르면 바로 올림·10MB, 담당 직원은 추가 때 후보에서 처음엔 나), 저장 전 떠나면 확인, 추가하면 그 계약 패널로 |
| `features/admin-contracts/components/pickers.tsx` | 담당 직원 후보 목록·변경 창, 다른 멘토로 옮기기 창(멘토 검색) |
| `features/admin-mentors/*` | 멘토 목록 상태에 '가입 전'(`status=pending`)·배지, 상세 '계약' 탭(카드 조회만, 계약 조회 권한이 있을 때), 가입 전 멘토는 [비활성화]/[활성화] 없음·계정 칸 '가입 전'·신청 받기 막음, 비활성화 확인 창 문구 수정 |
| `features/staff/nav.ts` | 레일 '행정 업무' 모듈 › '계약'(`educator.contract.read`) |
| `features/mentor-profile/api.ts` | S3 업로드 단계에 파일 이름 인자 |
| `routes/_staff/admin/administration/contracts.tsx`, `educators/mentors/*` | 계약 라우트, 멘토 상세 `tab=contracts`·목록 `status=pending` |

## 주요 결정 (사용자 결정, F83)
- 계약은 레일 '행정 업무' › '계약'(다른 행정 메뉴는 범위 밖). 표 + 오른쪽 패널.
- 멘토·강사 계약 둘 다. 멘토 상세 계약 탭은 조회만, 누르면 행정 업무 › 계약 패널.
- 멘토 목록에는 '가입 전' 상태만 더한다.

## 발견한 문제와 해결
- 추가를 저장하고 패널을 옮길 때, 저장 전 떠남 확인이 아직 바뀌지 않은 폼 상태로 이동을 막았다. 저장한 계약을 여는 이동은 `ignoreBlocker`로 한다.
- FE-18a 멘토 비활성화 확인 창이 '로그인이 막혀요'라고 안내했지만 멘토 비활성화(A35)는 로그인을 막지 않아 문구를 고쳤다.

## 범위에서 뺀 것
- 강사 계약의 연결: 강사 목록·검색 API와 가입하는 강사가 없어 강사 화면 때 더한다(F83).
- 계약 표의 '가입 전' 표시: 계약 응답의 연결 프로필에 가입 여부가 없어 이름만 보인다(멘토 목록·상세에서는 보인다).

## 검증
- `npm run lint`, `format:check`, `typecheck`, `test`(UTC·Asia/Seoul, 398개), `build`, `e2e`(49개)
- 1440 라이트·다크 화면 확인(계약 목록, 진행 중·작성 중 패널, 추가 패널, 멘토 계약 탭, 가입 전 멘토 상세, 멘토 목록)

## 사용자 확인
- 화면을 확인하고 병합을 승인함.

## 남은 작업
- FE-15a 보완(가입 승인 멘토 탭을 가입 전 멘토 고르기로), FE-18c 기수 배정·일정 대리.
