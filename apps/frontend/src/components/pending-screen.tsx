import { Spinner } from "./ui/spinner";

/** 세션 확인(refresh → /me) 등으로 화면이 늦으면 0.3초 뒤부터 가운데 스피너 (decisions F22). */
export function PendingScreen() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background">
      <Spinner />
    </div>
  );
}
