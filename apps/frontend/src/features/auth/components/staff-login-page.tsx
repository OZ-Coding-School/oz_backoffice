import { Link } from "@tanstack/react-router";

import { useSession } from "@/api/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { env } from "@/env";

import { GOOGLE_LOGIN_ERRORS, sessionEndedMessage } from "../messages";

/** Google "G" 로고 (Google 브랜드 가이드의 4색) */
function GoogleIcon() {
  return (
    <svg aria-hidden viewBox="0 0 18 18" className="size-4.5">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3.01-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}

/** 운영진 로그인 (Figma `Staff Default`·`Staff Google error`, decisions A1·A15·A61). */
export function StaffLoginPage({ error }: { error?: string | undefined }) {
  const endedReason = useSession((s) => s.endedReason);
  const alert =
    (error ? (GOOGLE_LOGIN_ERRORS[error] ?? GOOGLE_LOGIN_ERRORS.google_auth_failed) : null) ??
    sessionEndedMessage(endedReason);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-h1 text-foreground">운영진 로그인</h1>
        <p className="text-body text-muted-foreground">회사 Google 계정으로 로그인하세요.</p>
      </div>
      {alert ? <Alert variant={alert.variant} title={alert.title} description={alert.description} /> : null}
      <Button
        variant="outline"
        className="w-full"
        // 백엔드가 Google로 보내고, 콜백을 받아 refresh 쿠키를 둔 뒤 프론트로 돌려보낸다 (A15)
        onClick={() => window.location.assign(`${env.apiBaseUrl}/auth/google/login`)}
      >
        <GoogleIcon />
        Google 계정으로 로그인
      </Button>
      <ul className="flex flex-col gap-1 rounded-lg bg-muted px-4 py-3 text-caption text-muted-foreground">
        <li>· @nextrunners.co.kr 계정만 사용할 수 있어요.</li>
        <li>· 처음 로그인하면 소속·담당 정보를 입력하고 승인을 받아야 해요.</li>
      </ul>
      <p className="border-t border-border pt-6 text-center text-caption text-muted-foreground">
        수강생·멘토이신가요?{" "}
        <Link to="/login" className="text-caption-strong text-primary-text hover:underline">
          수강생·멘토 로그인
        </Link>
      </p>
    </div>
  );
}
