import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { CircleCheck, CircleX, Lock, Mail } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { PasswordInput } from "@/features/auth/components/password-input";
import { PasswordRules } from "@/features/auth/components/password-rules";
import { passwordSchema } from "@/features/auth/password";
import { formatSeconds, useCountdown } from "@/lib/use-countdown";
import { cn } from "@/lib/utils";

import { passwordChangeQuery, POLL_MS, useChangePassword, useSendPasswordLink } from "../api";
import { maskEmail } from "../mask";
import { FALLBACK_ERROR, PASSWORD_CHANGE_ERRORS } from "../messages";

const schema = z
  .object({ password: passwordSchema, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "비밀번호가 서로 달라요." });
type Form = z.infer<typeof schema>;

const LINK_MINUTES = 30;
const RESEND_SECONDS = 60;

function errorText(error: unknown): string {
  const code = error instanceof ApiError ? error.code : undefined;
  return (code && PASSWORD_CHANGE_ERRORS[code]) ?? FALLBACK_ERROR;
}

/**
 * 비밀번호 변경 창 (Figma `Screen / 비밀번호 변경 · 링크 보냄 / 인증됨`, A72·F37).
 * 링크를 보낸 뒤 창이 열려 있는 동안 5초마다 인증 여부를 확인하고, 인증되면 입력칸을 켠다.
 */
export function PasswordChangeDialog({
  email,
  open,
  onOpenChange,
}: {
  email: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const send = useSendPasswordLink();
  const change = useChangePassword();
  const [error, setError] = useState<string | null>(null);
  const status = useQuery({
    ...passwordChangeQuery,
    enabled: open,
    refetchInterval: (query) => (open && query.state.data?.state === "SENT" ? POLL_MS : false),
  });
  const state = status.data?.state ?? "NONE";
  const expiresAt = status.data?.expires_at ? new Date(status.data.expires_at).getTime() : null;
  const remaining = useCountdown(state === "VERIFIED" ? expiresAt : null);
  // 다시 보내기는 1분 간격 (A72): 보낸 시각 = 링크 만료 − 30분
  const sentAt = state === "SENT" && expiresAt ? expiresAt - LINK_MINUTES * 60_000 : null;
  const resendWait = useCountdown(sentAt === null ? null : sentAt + RESEND_SECONDS * 1000);

  const form = useForm<Form>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { password: "", confirm: "" },
  });
  const password = useWatch({ control: form.control, name: "password" });
  const confirm = useWatch({ control: form.control, name: "confirm" });
  const verified = state === "VERIFIED";

  const close = (next: boolean) => {
    if (!next) {
      form.reset();
      setError(null);
    }
    onOpenChange(next);
  };

  const resend = async () => {
    setError(null);
    try {
      await send.mutateAsync();
    } catch (e) {
      setError(errorText(e));
    }
  };

  const submit = form.handleSubmit(async ({ password: next }) => {
    setError(null);
    try {
      await change.mutateAsync(next);
      toast.success("비밀번호를 바꿨어요");
      close(false);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      if (code === "invalid_password") form.setError("password", { message: errorText(e) });
      else setError(errorText(e));
      if (code === "password_change_not_verified") void status.refetch();
    }
  });

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="flex max-w-130 flex-col gap-4 p-6">
        <div className="flex items-center gap-2.5 pr-8">
          <span aria-hidden className="inline-flex size-8 items-center justify-center rounded-full bg-accent">
            <Lock className="size-4 text-primary-text" />
          </span>
          <DialogTitle className="text-h2 text-foreground">비밀번호 변경</DialogTitle>
        </div>
        <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted px-4 py-3" aria-live="polite">
          {verified ? (
            <>
              <p className="text-body-strong text-foreground">이메일 인증이 완료되었습니다.</p>
              <DialogDescription className="text-caption text-muted-foreground">
                10분 안에 새 비밀번호를 저장해 주세요 · 남은 시간 {formatSeconds(remaining)}
              </DialogDescription>
            </>
          ) : state === "SENT" ? (
            <>
              <p className="text-body-strong text-foreground">{maskEmail(email)}으로 인증 링크를 보냈어요</p>
              <DialogDescription className="text-caption text-muted-foreground">
                메일의 [이메일 인증하기]를 누르면 여기서 새 비밀번호를 입력할 수 있어요 · 링크는 30분 동안 유효해요
              </DialogDescription>
            </>
          ) : (
            <>
              <p className="text-body-strong text-foreground">
                {send.isPending ? "인증 링크를 보내는 중이에요" : "인증 링크를 다시 받아 주세요"}
              </p>
              <DialogDescription className="text-caption text-muted-foreground">
                {maskEmail(email)}으로 인증 링크를 보내요. 링크를 누르면 여기서 새 비밀번호를 입력할 수 있어요
              </DialogDescription>
            </>
          )}
        </div>
        <form id="password-change" onSubmit={(e) => void submit(e)} className="flex flex-col gap-3">
          <FormField label="새 비밀번호" error={form.formState.errors.password?.message ?? undefined}>
            {(field) => (
              <PasswordInput
                {...field}
                {...form.register("password", { deps: ["confirm"] })}
                autoComplete="new-password"
                placeholder="새 비밀번호"
                disabled={!verified}
              />
            )}
          </FormField>
          <PasswordRules value={password} />
          <FormField label="새 비밀번호 확인">
            {(field) => (
              <PasswordInput
                {...field}
                {...form.register("confirm")}
                autoComplete="new-password"
                placeholder="한 번 더 입력하세요"
                disabled={!verified}
              />
            )}
          </FormField>
          <MatchHint password={password} confirm={confirm} />
        </form>
        <p
          className={cn(
            "flex items-start gap-2 rounded-md px-3 py-2 text-body-sm text-foreground",
            verified ? "bg-success-subtle" : "bg-accent",
          )}
        >
          {verified ? (
            <CircleCheck aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          ) : (
            <Mail aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          )}
          {verified
            ? "바꾼 뒤에도 지금 로그인은 유지돼요"
            : "메일이 안 왔다면 스팸함을 확인하거나 1분 뒤 다시 보내 주세요"}
        </p>
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          {verified ? (
            <Button variant="ghost" onClick={() => close(false)}>
              닫기
            </Button>
          ) : (
            <Button variant="ghost" onClick={() => void resend()} disabled={send.isPending || resendWait > 0}>
              {resendWait > 0 ? `다시 보내기 (${resendWait}초)` : "다시 보내기"}
            </Button>
          )}
          <Button
            type="submit"
            form="password-change"
            disabled={!verified || !form.formState.isValid || change.isPending}
          >
            변경 저장
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 확인 칸 일치 여부 (F37): 입력하기 시작하면 바로 보여 준다 */
function MatchHint({ password, confirm }: { password: string; confirm: string }) {
  if (!confirm) return null;
  const same = password === confirm;
  const Icon = same ? CircleCheck : CircleX;
  return (
    <p
      role="status"
      className={cn("-mt-1 flex items-center gap-2 text-caption", same ? "text-success-text" : "text-destructive-text")}
    >
      <Icon aria-hidden className="size-4" />
      {same ? "비밀번호가 일치해요" : "비밀번호가 서로 달라요"}
    </p>
  );
}
