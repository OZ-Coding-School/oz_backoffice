import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { CircleX, Hourglass } from "lucide-react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import {
  authKeys,
  logout,
  meQuery,
  memberSignupQuery,
  signupCohortsQuery,
  type Me,
  type MemberSignup,
  type SignupCohort,
} from "../api";
import { homePath } from "../navigation";

const TYPE_LABEL = { STUDENT: "수강생", MENTOR: "멘토" } as const;

function cohortLabel(cohorts: SignupCohort[] | undefined, id: string | null | undefined): string {
  const cohort = cohorts?.find((c) => c.cohort_id === id);
  return cohort ? `${cohort.bootcamp_name} ${cohort.cohort_number}기` : "-";
}

/**
 * 로그인 후 승인 전 회원의 가입 상태 모달 (Figma `가입 상태 (모달)`, decisions A33).
 * 닫기·확인은 로그아웃하고 로그인 화면에 남는다.
 */
export function SignupStatusDialog({ me, onDone }: { me: Me; onDone: (me: Me | null) => void }) {
  const signup = useQuery(memberSignupQuery);
  const cohorts = useQuery(signupCohortsQuery);
  const close = async () => {
    await logout();
    onDone(null);
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : void close())}>
      <DialogContent className="flex max-w-130 flex-col gap-6 px-6 pt-7 pb-6 md:px-10 md:pt-10 md:pb-10">
        {!signup.data ? (
          <div className="flex justify-center py-10">
            <Spinner />
            <DialogTitle className="sr-only">가입 상태</DialogTitle>
          </div>
        ) : me.approval_status === "REJECTED" ? (
          <RejectedContent signup={signup.data} cohorts={cohorts.data} onClose={close} onDone={onDone} />
        ) : (
          <PendingContent me={me} signup={signup.data} cohorts={cohorts.data} onClose={close} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function StatusIcon({ tone }: { tone: "warning" | "error" }) {
  const Icon = tone === "warning" ? Hourglass : CircleX;
  return (
    <span
      className={cn(
        "inline-flex size-14 items-center justify-center rounded-full",
        tone === "warning" ? "bg-warning-subtle text-warning-text" : "bg-destructive-subtle text-destructive-text",
      )}
    >
      <Icon aria-hidden className="size-6" />
    </span>
  );
}

function PendingContent({
  me,
  signup,
  cohorts,
  onClose,
}: {
  me: Me;
  signup: MemberSignup;
  cohorts: SignupCohort[] | undefined;
  onClose: () => void;
}) {
  const mentor = signup.signup_type === "MENTOR";
  const rows: [string, string][] = [
    ["가입 유형", TYPE_LABEL[signup.signup_type]],
    ...(mentor ? [] : ([["신청 기수", cohortLabel(cohorts, signup.requested_cohort_id)]] as [string, string][])),
    ["이름", me.name],
    ["신청일", signup.created_at ? formatKst(signup.created_at, "yyyy-MM-dd") : "-"],
  ];
  return (
    <>
      <StatusIcon tone="warning" />
      <div className="flex flex-col gap-2">
        <DialogTitle className="text-h1">가입 승인을 기다리고 있어요</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          입력한 정보가 {mentor ? "멘토 계약 정보" : "수강생 명단"}과 바로 맞지 않아 담당 매니저가 확인하고 있어요.
          승인되면 가입한 이메일로 알려 드려요.
        </DialogDescription>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 rounded-lg bg-muted px-4 py-3 text-body-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-body-strong text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex justify-end">
        <Button onClick={onClose}>확인</Button>
      </div>
    </>
  );
}

const reapplySchema = z
  .object({
    signup_type: z.enum(["STUDENT", "MENTOR"]),
    cohort_id: z.string().optional(),
    nickname: z.string().trim().max(30, "닉네임은 30자 이내로 입력해 주세요.").optional(),
    display_name_preference: z.enum(["NAME", "NICKNAME"]),
  })
  .superRefine((v, ctx) => {
    if (v.signup_type === "STUDENT" && !v.cohort_id) {
      ctx.addIssue({ code: "custom", path: ["cohort_id"], message: "신청 기수를 골라 주세요." });
    }
    if (v.signup_type === "MENTOR" && v.display_name_preference === "NICKNAME" && !v.nickname) {
      ctx.addIssue({ code: "custom", path: ["nickname"], message: "닉네임을 보이게 하려면 닉네임을 입력해 주세요." });
    }
  });
type ReapplyValues = z.infer<typeof reapplySchema>;

function RejectedContent({
  signup,
  cohorts,
  onClose,
  onDone,
}: {
  signup: MemberSignup;
  cohorts: SignupCohort[] | undefined;
  onClose: () => void;
  onDone: (me: Me | null) => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const form = useForm<ReapplyValues>({
    resolver: zodResolver(reapplySchema),
    defaultValues: {
      signup_type: signup.signup_type,
      cohort_id: signup.requested_cohort_id ?? undefined,
      nickname: signup.nickname ?? "",
      display_name_preference: signup.display_name_preference ?? "NAME",
    },
  });
  const type = useWatch({ control: form.control, name: "signup_type" });
  const { errors } = form.formState;

  const reapply = useMutation({
    mutationFn: (values: ReapplyValues) =>
      unwrap(
        api.POST("/api/v1/me/member-signup", {
          body:
            values.signup_type === "STUDENT"
              ? { signup_type: "STUDENT", cohort_id: values.cohort_id ?? null }
              : {
                  signup_type: "MENTOR",
                  nickname: values.nickname || null,
                  display_name_preference: values.display_name_preference,
                },
        }),
      ),
    onSuccess: async (applicant) => {
      queryClient.setQueryData(authKeys.memberSignup, applicant.signup);
      const me = await queryClient.fetchQuery({ ...meQuery, staleTime: 0 });
      if (me.approval_status === "APPROVED") {
        toast.success("가입이 승인됐어요", { description: "바로 이용할 수 있어요." });
        onDone(me);
        await navigate({ href: homePath(me), replace: true });
        return;
      }
      onDone(me); // 다시 대기면 승인 대기 모달을 보여 준다
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "invalid_cohort") {
        form.setError("cohort_id", { message: "가입할 수 있는 기수를 골라 주세요." });
        return;
      }
      if (error instanceof ApiError) {
        for (const [field, message] of Object.entries(error.fieldErrors)) {
          form.setError(field as keyof ReapplyValues, { message });
        }
      }
      form.setError("root", { message: error instanceof ApiError ? error.message : "잠시 후 다시 시도해 주세요." });
    },
  });

  return (
    <>
      <StatusIcon tone="error" />
      <div className="flex flex-col gap-2">
        <DialogTitle className="text-h1">가입이 반려됐어요</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          사유를 확인하고 정보를 고쳐 다시 신청해 주세요.
        </DialogDescription>
      </div>
      <Alert variant="error" title="반려 사유" description={signup.reject_reason ?? "사유가 없어요."} />
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={form.handleSubmit((values) => reapply.mutate(values))}
        id="reapply-form"
      >
        <div className="flex flex-col gap-2">
          <span className="text-label text-foreground" id="signup-type-label">
            가입 유형
          </span>
          <Controller
            control={form.control}
            name="signup_type"
            render={({ field }) => (
              <RadioGroup aria-labelledby="signup-type-label" value={field.value} onValueChange={field.onChange}>
                <RadioGroupItem value="STUDENT">수강생</RadioGroupItem>
                <RadioGroupItem value="MENTOR">멘토</RadioGroupItem>
              </RadioGroup>
            )}
          />
        </div>
        {type === "STUDENT" ? (
          <FormField label="신청 기수" error={errors.cohort_id?.message}>
            {(field) => (
              <Controller
                control={form.control}
                name="cohort_id"
                render={({ field: control }) => (
                  <Select value={control.value ?? ""} onValueChange={control.onChange}>
                    <SelectTrigger {...field}>
                      <SelectValue placeholder="기수를 골라 주세요" />
                    </SelectTrigger>
                    <SelectContent>
                      {(cohorts ?? []).map((c) => (
                        <SelectItem key={c.cohort_id} value={c.cohort_id}>
                          {c.bootcamp_name} {c.cohort_number}기
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            )}
          </FormField>
        ) : (
          <>
            <FormField
              label="닉네임 (선택)"
              helper="수강생에게 보일 이름을 닉네임으로 할 수 있어요."
              error={errors.nickname?.message}
            >
              {(field) => <Input {...field} {...form.register("nickname")} placeholder="30자 이내" maxLength={30} />}
            </FormField>
            <div className="flex flex-col gap-2">
              <span className="text-label text-foreground" id="display-name-label">
                수강생에게 보일 이름
              </span>
              <Controller
                control={form.control}
                name="display_name_preference"
                render={({ field }) => (
                  <RadioGroup aria-labelledby="display-name-label" value={field.value} onValueChange={field.onChange}>
                    <RadioGroupItem value="NAME">이름</RadioGroupItem>
                    <RadioGroupItem value="NICKNAME">닉네임</RadioGroupItem>
                  </RadioGroup>
                )}
              />
            </div>
          </>
        )}
        {errors.root ? <p className="text-caption text-destructive-text">{errors.root.message}</p> : null}
      </form>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>
          닫기
        </Button>
        <Button type="submit" form="reapply-form" disabled={reapply.isPending}>
          다시 신청하기
        </Button>
      </div>
    </>
  );
}
