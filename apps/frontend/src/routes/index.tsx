import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: Home,
});

/** 화면 구현 전 자리표시 (로그인·운영진 화면은 다음 PR에서). */
function Home() {
  return (
    <main>
      <h1>오즈코딩스쿨 운영 행정 지원 플랫폼</h1>
      <p>화면을 준비하고 있습니다.</p>
    </main>
  );
}
