import { zodResolver } from "@hookform/resolvers/zod";
import { Mail, Pencil, ShieldCheck, Smartphone } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { FormField, InputIcon } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatSeconds, useCountdown } from "@/lib/use-countdown";

import { VERIFICATION_ERRORS, type AlertMessage } from "../messages";
import { CODE_TTL_SECONDS, RESEND_SECONDS, rateLimitAlert } from "../signup/verification";

const codeSchema = z.object({ code: z.string().regex(/^\d{6}$/, "6자리 숫자를 입력해 주세요.") });

/**
 * 인증코드 확인 (Figma `이메일 코드 확인`·`휴대폰 인증`·`오류 · 코드 불일치`).
 * 보낸 대상은 고칠 수 없게 보여 주고(연필 → 다시 입력), 남은 시간과 재발송 대기를 함께 보여 준다.
 */
export function CodeVerify({
  kind,
  target,
  sentAt,
  onEdit,
  onResend,
  onVerify,
}: {
  kind: "email" | "phone";
  target: string;
  sentAt: number;
  onEdit: () => void;
  onResend: () => Promise<void>;
  onVerify: (code: string) => Promise<void>;
}) {
  const [alert, setAlert] = useState<AlertMessage | null>(null);
  const [resendAt, setResendAt] = useState(sentAt + RESEND_SECONDS * 1000);
  const expiresIn = useCountdown(sentAt + CODE_TTL_SECONDS * 1000);
  const resendIn = useCountdown(resendAt);
  const form = useForm<z.infer<typeof codeSchema>>({ resolver: zodResolver(codeSchema), defaultValues: { code: "" } });
  const label = kind === "email" ? "이메일" : "휴대폰 번호";

  const onSubmit = form.handleSubmit(async ({ code }) => {
    setAlert(null);
    try {
      await onVerify(code);
    } catch (error) {
      const message = error instanceof ApiError ? VERIFICATION_ERRORS[error.code] : undefined;
      if (message) {
        form.setError("code", {
          message:
            error instanceof ApiError && error.code === "invalid_verification_code"
              ? `${message} 5번 틀리면 코드를 새로 받아야 해요.`
              : message,
        });
        return;
      }
      throw error;
    }
  });

  const resend = async () => {
    setAlert(null);
    try {
      await onResend();
      setResendAt(Date.now() + RESEND_SECONDS * 1000);
      form.resetField("code");
    } catch (error) {
      const limited = rateLimitAlert(error);
      if (limited) {
        setResendAt(limited.until.getTime());
        setAlert(limited);
        return;
      }
      throw error;
    }
  };

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
      {alert ? <Alert variant={alert.variant} title={alert.title} description={alert.description} /> : null}
      <div className="flex flex-col gap-4">
        <FormField label={label}>
          {(field) => (
            <div className="relative">
              <InputIcon icon={kind === "email" ? Mail : Smartphone} />
              <Input {...field} value={target} disabled className="pr-10 pl-9" />
              <button
                type="button"
                onClick={onEdit}
                aria-label={`${label} 다시 입력`}
                className="absolute top-1/2 right-2 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Pencil aria-hidden className="size-4" />
              </button>
            </div>
          )}
        </FormField>
        <FormField label="인증코드" error={form.formState.errors.code?.message}>
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
        <div className="flex items-center justify-between text-caption text-muted-foreground">
          <span>
            {expiresIn > 0 ? `남은 시간 ${formatSeconds(expiresIn)}` : "코드가 만료됐어요. 다시 받아 주세요."}
          </span>
          {resendIn > 0 ? (
            <span>코드 다시 받기 ({resendIn}초)</span>
          ) : (
            <button type="button" onClick={resend} className="text-caption-strong text-primary-text hover:underline">
              코드 다시 받기
            </button>
          )}
        </div>
      </div>
      <Button type="submit" disabled={form.formState.isSubmitting} className="w-full">
        확인
      </Button>
    </form>
  );
}
