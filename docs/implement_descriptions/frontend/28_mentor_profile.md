# 28. FE-12b 멘토 내 프로필

- 상태: 완료 (2026-11-24 병합)
- 관련 PR: #122
- 관련 결정: `docs/decisions.md` F56 (F54·A22·A28·F30·F37·A72)
- 이전 기록: [27. FE-12a 멘토 정산 목록·명세](27_mentor_settlements.md)

## 배경
FE-12의 마지막 PR이다(F54). 멘토가 수강생에게 보이는 자기 프로필(사진·보일 이름·한 줄 소개·전문 분야·소개)을 고치고, 배정된 기수와 계정을 본다. 백엔드 API(`/me/mentor-profile`, 사진 업로드·확정·삭제, `/me/mentor-assignments`)는 P6·P8에서 만들어 두었다.

시안은 데스크톱만 있었다(`Screen / 내 프로필`). 구현 전에 Figma에 그렸다(F49 배치).
- 각 크기 Section: `내 프로필 (FE-12b)`. 데스크톱은 FE-2 사이드바(내 공간 › 내 프로필), 태블릿·휴대폰은 한 열.

## 구현 내용

| 파일 | 내용 |
| --- | --- |
| `features/mentor-profile/api.ts` | `mentorProfileQuery`, `useSaveMentorProfile`(글 PATCH → 사진 업로드 표 → S3 POST(fields + `file`) → 확정, 또는 DELETE). 마지막 응답으로 캐시를 고친다 |
| `features/mentor-profile/image.ts` | `photoProblem`(형식·10MB), `centerSquare`, `toProfilePhoto`(canvas로 가운데 정사각형 → 512 WebP 0.85, 2MB 확인) |
| `features/mentor-profile/form.ts` | zod 입력 규칙(길이, 닉네임으로 보이려면 닉네임 필요, 전문 분야 합쳐 200자), `formOf`·`bodyOf`(빈 값 null), `displayNameOf`, `addChip` |
| `features/mentor-profile/labels.ts` | 배정 기수 정렬·기간·정산 기준 |
| `features/mentor-profile/components/mentor-profile-page.tsx` | 편집 폼(react-hook-form), 사진 미리 보기, 배정된 기수, 계정(비밀번호 재설정 창 재사용), 미리보기 창, 떠날 때 확인(`useBlocker`) |
| `features/mentor-profile/components/expertise-input.tsx` | 칩 입력(Enter·쉼표, 한글 조합 중 Enter 무시, 빈 칸 Backspace, 칩 빼기, 벗어나면 넣기) |
| `features/apply/components/mentor-dialog.tsx` | 본문을 `MentorIntro`로 빼서 미리보기와 같이 쓴다 |
| `routes/_member/my/profile.tsx` | 수강생·멘토 모두. 계정 종류에 따라 미리 불러오기와 화면을 나눈다 |
| `features/member/nav.ts` | 멘토 '내 공간 › 내 프로필' |

- 사진 원본은 10MB까지 고를 수 있고, 서버에는 줄인 WebP만 보낸다(서버 한도 2MB, A28).
- 저장 순서는 글 → 사진이다. 사진이 실패하면 글은 저장된 채로 오류를 알리고, 사진은 다시 저장할 수 있게 남긴다.

## 주요 결정 (사용자 결정, F56)
- 2단 화면, '내 공간 › 내 프로필', 정사각 512px WebP, 미리보기 넣기, 사진도 [저장] 때 함께, 떠날 때 확인, 배정 기수는 종료까지 모두.

## 검증
- `lint`, `typecheck`, `format:check`, `build` 통과
- `vitest` 276 passed (TZ=UTC·America/Los_Angeles·Asia/Seoul). 새 테스트: 입력 변환·규칙·칩·사진 검사·배정 정렬, 화면(표시·한 번에 저장·사진 업로드·사진 삭제·형식 오류·미리보기·떠날 때 확인·서버 오류)
- `playwright` 34 passed. 새 E2E: 데스크톱 메뉴 → 사진(900×600 PNG가 실제 브라우저에서 512×512 WebP로) + 한 줄 소개 저장, 휴대폰 더보기 → 내 프로필 → 떠날 때 확인
- 390·768·1440 화면과 미리보기 창을 시안과 비교했다

- GitHub Actions (PR #122): 첫 실행이 문서 커밋 push로 취소된 뒤 건너뛰어져 다시 돌려 통과를 확인했다(원인은 #123에서 고쳤다, 구현 기록 backend/81). develop rebase 후 다시 통과
- 사용자가 병합을 확인했다(2026-11-24)

## 남은 작업
- FE-13 멘토 홈
