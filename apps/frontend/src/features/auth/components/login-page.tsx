import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Mail } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { useSession } from "@/api/session";
import { FormField, InputIcon } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatKst, secondsFromNow } from "@/lib/datetime";

import { login, type Me } from "../api";
import { LOGIN_ERRORS, sessionEndedMessage, type AlertMessage } from "../messages";
import { afterLoginPath, needsSignupStatus } from "../navigation";
import { emailSchema } from "../password";
import { PasswordInput as PasswordField } from "./password-input";
import { SignupStatusDialog } from "./signup-status-dialog";

const schema = z.object({
  email: emailSchema,
  password: z.string().min(1, "비밀번호를 입력해 주세요."),
});
type Values = z.infer<typeof schema>;

/** 수강생·멘토 로그인 (Figma `Login / Default·Invalid·Locked`, decisions A32·F20). */
export function LoginPage({ me, redirect, email }: { me: Me | null; redirect?: string; email?: string }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const endedReason = useSession((s) => s.endedReason);
  const [alert, setAlert] = useState<AlertMessage | null>(null);
  const [lockedUntil, setLockedUntil] = useState<Date | null>(null);
  const [member, setMember] = useState<Me | null>(needsSignupStatus(me) ? me : null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: email ?? "", password: "" } });
  const { errors, isSubmitting } = form.formState;

  // 잠금 시각이 지나면 다시 입력할 수 있게 한다
  useEffect(() => {
    if (!lockedUntil) return;
    const timer = window.setTimeout(() => {
      setLockedUntil(null);
      setAlert(null);
    }, lockedUntil.getTime() - Date.now());
    return () => window.clearTimeout(timer);
  }, [lockedUntil]);

  const ended = alert ? null : sessionEndedMessage(endedReason);
  const shown = alert ?? ended;
  const locked = lockedUntil !== null;

  const onSubmit = form.handleSubmit(async (values) => {
    setAlert(null);
    try {
      const signedIn = await login(queryClient, values);
      if (needsSignupStatus(signedIn)) {
        setMember(signedIn);
        return;
      }
      await navigate({ href: afterLoginPath(signedIn, redirect), replace: true });
    } catch (error) {
      form.resetField("password");
      if (error instanceof ApiError && error.code === "login_locked") {
        const until = secondsFromNow(error.retryAfterSeconds ?? 15 * 60);
        setLockedUntil(until);
        setAlert({
          variant: "warning",
          title: "로그인이 잠시 잠겼어요",
          description: `5번 연속 실패해 ${formatKst(until, "HH:mm")}부터 다시 시도할 수 있어요. 비밀번호를 재설정하면 바로 로그인할 수 있어요.`,
        });
        return;
      }
      const known = error instanceof ApiError ? LOGIN_ERRORS[error.code] : undefined;
      setAlert(
        known ?? {
          variant: "error",
          title: "로그인하지 못했어요",
          description: error instanceof ApiError ? error.message : "잠시 후 다시 시도해 주세요.",
        },
      );
    }
  });

  return (
    <>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-h1 text-foreground">로그인</h1>
          <p className="text-body text-muted-foreground">수강생·멘토 계정의 이메일과 비밀번호로 로그인하세요.</p>
        </div>
        {shown ? <Alert variant={shown.variant} title={shown.title} description={shown.description} /> : null}
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
          <div className="flex flex-col gap-4">
            <FormField label="이메일" error={errors.email?.message}>
              {(field) => (
                <div className="relative">
                  <InputIcon icon={Mail} />
                  <Input
                    {...field}
                    {...form.register("email")}
                    type="email"
                    autoComplete="email"
                    placeholder="name@example.com"
                    className="pl-9"
                  />
                </div>
              )}
            </FormField>
            <FormField label="비밀번호" error={errors.password?.message}>
              {(field) => (
                <PasswordField
                  {...field}
                  {...form.register("password")}
                  disabled={locked}
                  autoComplete="current-password"
                  placeholder="비밀번호를 입력하세요"
                />
              )}
            </FormField>
            <Link to="/password-reset" className="self-end text-label text-primary-text hover:underline">
              비밀번호를 잊으셨나요?
            </Link>
          </div>
          <Button type="submit" disabled={locked || isSubmitting} className="w-full">
            {locked && lockedUntil ? `${formatKst(lockedUntil, "HH:mm")} 이후 다시 시도` : "로그인"}
          </Button>
        </form>
        <p className="text-center text-body text-muted-foreground">
          아직 계정이 없나요?{" "}
          <Link to="/signup" className="text-body-strong text-primary-text hover:underline">
            수강생·멘토 가입
          </Link>
        </p>
        <p className="text-center text-caption text-muted-foreground">
          운영진이신가요?{" "}
          <a href="/staff/login" className="text-caption-strong text-primary-text hover:underline">
            운영진 로그인
          </a>
        </p>
      </div>
      {member ? (
        <SignupStatusDialog me={member} onDone={(next) => setMember(needsSignupStatus(next) ? next : null)} />
      ) : null}
    </>
  );
}
