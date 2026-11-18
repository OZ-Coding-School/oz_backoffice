import { useNavigate } from "@tanstack/react-router";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { logout, type Me } from "../api";
import { ROLE_LABELS } from "../messages";
import { Logo } from "./auth-layout";

/** 로그인 후 임시 홈 (Figma `임시 홈`, decisions F20). 회원 틀(FE-2)·운영진 틀(FE-14)에서 바꾼다. */
export function TempHome({ me }: { me: Me }) {
  const navigate = useNavigate();
  const roles = [...new Set(me.roles.map((r) => ROLE_LABELS[r.role] ?? r.role))];
  const area = me.account_type === "STAFF" ? "운영 업무" : "멘토링";
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-4">
      <section className="flex w-full flex-col gap-5 rounded-xl border border-border bg-card p-8 shadow-sm md:max-w-110">
        <Logo />
        <div className="flex flex-col gap-2">
          <h1 className="text-h1 text-foreground">안녕하세요, {me.name}님</h1>
          {roles.length ? (
            <div className="flex flex-wrap gap-1.5">
              {roles.map((role) => (
                <Badge key={role}>{role}</Badge>
              ))}
            </div>
          ) : null}
        </div>
        <p className="text-body text-muted-foreground">
          화면을 준비하고 있어요. 곧 이곳에서 {area}를 이용할 수 있어요.
        </p>
        <Button
          variant="outline"
          className="w-full"
          onClick={async () => {
            await logout();
            await navigate({ to: "/login", replace: true });
          }}
        >
          로그아웃
        </Button>
      </section>
    </main>
  );
}
