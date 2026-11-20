import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Mail, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import { FormField, InputIcon } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatKst, secondsFromNow } from "@/lib/datetime";
import { formatSeconds, useCountdown } from "@/lib/use-countdown";

import { VERIFICATION_ERRORS, type AlertMessage } from "../messages";
import { emailSchema, passwordSchema } from "../password";
import { PasswordInput } from "./password-input";
import { PasswordRules } from "./password-rules";

/** 코드는 60초에 한 번 다시 받을 수 있다 (A32, 가입 코드와 같은 규칙). */
const RESEND_SECONDS = 60;

function rateLimitMessage(error: unknown): AlertMessage | null {
  if (!(error instanceof ApiError) || error.status !== 429) return null;
  const until = formatKst(secondsFromNow(error.retryAfterSeconds ?? 60), "HH:mm");
  return { variant: "warning", title: "요청이 너무 많아요", description: `${until}부터 다시 시도할 수 있어요.` };
}

function BackToLogin() {
  return (
    <Link
      to="/login"
      className="inline-flex items-center gap-1.5 self-start text-body-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft aria-hidden className="size-4" />
      로그인으로 돌아가기
    </Link>
  );
}

/**
 * 비밀번호 재설정 (Figma `Reset 1·2·2 Error·done`, decisions A32).
 * 단계는 화면 상태에만 두어 새로고침하면 1단계부터 다시 한다 (F22).
 */
export function PasswordResetPage() {
  const [email, setEmail] = useState<string | null>(null);
  return email ? <CodeStep email={email} /> : <EmailStep onSent={setEmail} />;
}

const emailForm = z.object({ email: emailSchema });

function EmailStep({ onSent }: { onSent: (email: string) => void }) {
  const [alert, setAlert] = useState<AlertMessage | null>(null);
  const form = useForm<z.infer<typeof emailForm>>({ resolver: zodResolver(emailForm), defaultValues: { email: "" } });
  const onSubmit = form.handleSubmit(async ({ email }) => {
    setAlert(null);
    try {
      await unwrap(api.POST("/api/v1/auth/password-reset/code", { body: { email } }));
      onSent(email); // 가입 여부와 상관없이 항상 다음 단계로 (A32)
    } catch (error) {
      setAlert(
        rateLimitMessage(error) ?? {
          variant: "error",
          title: "코드를 보내지 못했어요",
          description: error instanceof ApiError ? error.message : "잠시 후 다시 시도해 주세요.",
        },
      );
    }
  });
  return (
    <div className="flex flex-col gap-6">
      <BackToLogin />
      <div className="flex flex-col gap-2">
        <h1 className="text-h1 text-foreground">비밀번호 재설정</h1>
        <p className="text-body text-muted-foreground">가입한 이메일을 입력하면 6자리 인증코드를 보내 드려요.</p>
      </div>
      {alert ? <Alert variant={alert.variant} title={alert.title} description={alert.description} /> : null}
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
        <FormField label="이메일" helper="코드는 10분 동안 쓸 수 있어요." error={form.formState.errors.email?.message}>
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
        <Button type="submit" disabled={form.formState.isSubmitting} className="w-full">
          인증코드 받기
        </Button>
      </form>
      <p className="text-center text-caption text-muted-foreground">
        운영진은 Google 계정으로 로그인해 비밀번호가 없어요.
      </p>
    </div>
  );
}

const codeForm = z
  .object({
    code: z.string().regex(/^\d{6}$/, "6자리 숫자를 입력해 주세요."),
    password: passwordSchema,
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "비밀번호가 서로 달라요." });
type CodeValues = z.infer<typeof codeForm>;

function CodeStep({ email }: { email: string }) {
  const navigate = useNavigate();
  const [alert, setAlert] = useState<AlertMessage | null>(null);
  const [resendAt, setResendAt] = useState<number | null>(() => Date.now() + RESEND_SECONDS * 1000);
  const remaining = useCountdown(resendAt);
  const form = useForm<CodeValues>({
    resolver: zodResolver(codeForm),
    mode: "onChange",
    defaultValues: { code: "", password: "", confirm: "" },
  });
  const password = useWatch({ control: form.control, name: "password" });
  const { errors, isValid, isSubmitting } = form.formState;

  const resend = async () => {
    setAlert(null);
    try {
      await unwrap(api.POST("/api/v1/auth/password-reset/code", { body: { email } }));
      setResendAt(Date.now() + RESEND_SECONDS * 1000);
      form.resetField("code");
    } catch (error) {
      if (error instanceof ApiError && error.code === "resend_too_soon" && error.retryAfterSeconds) {
        setResendAt(Date.now() + error.retryAfterSeconds * 1000);
        return;
      }
      setAlert(rateLimitMessage(error) ?? { variant: "error", title: "코드를 보내지 못했어요" });
    }
  };

  const onSubmit = form.handleSubmit(async (values) => {
    setAlert(null);
    try {
      await unwrap(
        api.POST("/api/v1/auth/password-reset", { body: { email, code: values.code, new_password: values.password } }),
      );
      toast.success("비밀번호를 바꿨어요", { description: "새 비밀번호로 로그인해 주세요." });
      await navigate({ to: "/login", search: { email } });
    } catch (error) {
      const codeMessage = error instanceof ApiError ? VERIFICATION_ERRORS[error.code] : undefined;
      if (codeMessage) {
        form.setError("code", { message: codeMessage });
        return;
      }
      if (error instanceof ApiError && error.code === "invalid_password") {
        form.setError("password", { message: error.message });
        return;
      }
      setAlert(
        rateLimitMessage(error) ?? {
          variant: "error",
          title: "비밀번호를 바꾸지 못했어요",
          description: error instanceof ApiError ? error.message : "잠시 후 다시 시도해 주세요.",
        },
      );
    }
  });

  return (
    <div className="flex flex-col gap-6">
      <BackToLogin />
      <div className="flex flex-col gap-2">
        <h1 className="text-h1 text-foreground">새 비밀번호 만들기</h1>
        <p className="text-body text-muted-foreground">메일로 받은 인증코드와 새 비밀번호를 입력하세요.</p>
      </div>
      {alert ? (
        <Alert variant={alert.variant} title={alert.title} description={alert.description} />
      ) : (
        <Alert
          variant="info"
          title="메일을 확인해 주세요"
          description={`${email}으로 코드를 보냈어요. 가입한 이메일이 아니면 메일이 가지 않아요.`}
        />
      )}
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <FormField
            label="인증코드"
            error={errors.code?.message}
            helper={
              remaining > 0 ? (
                `코드 다시 받기는 ${formatSeconds(remaining)} 뒤에 할 수 있어요.`
              ) : (
                <button
                  type="button"
                  onClick={resend}
                  className="text-caption-strong text-primary-text hover:underline"
                >
                  코드 다시 받기
                </button>
              )
            }
          >
            {(field) => (
              <div className="relative">
                <InputIcon icon={ShieldCheck} />
                <Input
                  {...field}
                  {...form.register("code")}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="6자리 숫자"
                  className="pl-9"
                />
              </div>
            )}
          </FormField>
          <FormField label="새 비밀번호" error={undefined}>
            {(field) => (
              <PasswordInput
                {...field}
                {...form.register("password")}
                autoComplete="new-password"
                placeholder="새 비밀번호"
              />
            )}
          </FormField>
          <PasswordRules value={password} />
          <FormField label="새 비밀번호 확인" error={errors.confirm?.message}>
            {(field) => (
              <PasswordInput
                {...field}
                {...form.register("confirm", { deps: ["password"] })}
                autoComplete="new-password"
                placeholder="한 번 더 입력하세요"
              />
            )}
          </FormField>
        </div>
        <Button type="submit" disabled={!isValid || isSubmitting} className="w-full">
          비밀번호 변경
        </Button>
      </form>
    </div>
  );
}
