import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, BookOpen, CircleCheck, CircleX, Hourglass, Mail, Smartphone, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import { FormField, InputIcon } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatKst } from "@/lib/datetime";
import { useCountdown } from "@/lib/use-countdown";
import { cn } from "@/lib/utils";

import { signupCohortsQuery } from "../api";
import { emailSchema, PASSWORD_RULES, passwordSchema } from "../password";
import { signupApi, isSessionExpired } from "../signup/api";
import { formatPhone, isValidPhone, phoneDigits } from "../signup/phone";
import { tokenAlive, useSignupState, type SignupState, type SignupType } from "../signup/state";
import { PasswordInput } from "./password-input";
import { rateLimitAlert } from "../signup/verification";
import { CodeVerify } from "./signup-verify";
import { Stepper } from "./stepper";

const STEPS = ["가입 유형", "이메일 인증", "휴대폰 인증", "가입 정보"];
type Done = { type: SignupType; approved: boolean; email: string };

/**
 * 회원가입 마법사 (Figma `회원가입`, decisions F10·F24, A30·A31).
 * 가입 유형 → 이메일 인증(가입 토큰 30분) → 휴대폰 인증 → 가입 정보 → 완료.
 */
export function SignupPage() {
  const { state, update, reset } = useSignupState();
  const [done, setDone] = useState<Done | null>(null);
  const [expired, setExpired] = useState(() => state.signupToken !== null && !tokenAlive(state));

  if (done) return <SignupDone {...done} />;
  if (expired) {
    return (
      <Frame step={3} title="가입 정보" description="보안을 위해 인증 후 시간이 지나면 다시 인증해야 해요.">
        <Alert
          variant="error"
          title="인증 시간이 지났어요"
          description="이메일 인증 후 30분 안에 가입을 마쳐야 해요. 처음부터 다시 진행해 주세요."
        />
        <Button
          className="w-full"
          onClick={() => {
            reset();
            setExpired(false);
          }}
        >
          처음부터 다시
        </Button>
      </Frame>
    );
  }
  /** 가입 토큰이 만료됐다는 응답이면 만료 화면, 아니면 그대로 던진다 */
  const guard = async (task: () => Promise<void>) => {
    try {
      await task();
    } catch (error) {
      if (isSessionExpired(error)) {
        setExpired(true);
        return;
      }
      throw error;
    }
  };

  switch (state.step) {
    case "type":
      return <TypeStep value={state.type} onNext={(type) => update({ type, step: "email" })} />;
    case "email":
      return (
        <Frame
          step={1}
          title="이메일 인증"
          description="로그인에 쓸 이메일로 6자리 인증코드를 보내 드려요."
          back={{ label: "가입 유형 다시 고르기", onClick: () => update({ step: "type" }) }}
        >
          <EmailEntry
            type={state.type}
            initial={state.email}
            onSent={(email) => update({ email, emailSentAt: Date.now(), step: "email-code" })}
          />
        </Frame>
      );
    case "email-code":
      return (
        <Frame
          step={1}
          title="이메일 인증"
          description={`${state.email}으로 보낸 6자리 코드를 입력하세요.`}
          back={{ label: "가입 유형 다시 고르기", onClick: () => update({ step: "type" }) }}
        >
          <CodeVerify
            kind="email"
            target={state.email}
            sentAt={state.emailSentAt ?? 0}
            onEdit={() => update({ step: "email" })}
            onResend={() => signupApi.sendEmailCode(state.email)}
            onVerify={async (code) => {
              const token = await signupApi.verifyEmailCode(state.email, code);
              update({
                signupToken: token.signup_token,
                tokenExpiresAt: Date.now() + token.expires_in * 1000,
                step: "phone",
              });
            }}
          />
        </Frame>
      );
    case "phone":
      return (
        <Frame step={2} title="휴대폰 인증" description={phoneDescription(state.type)}>
          <PhoneEntry
            initial={state.phone}
            onSend={(phone) =>
              guard(async () => {
                await signupApi.sendPhoneCode(state.signupToken ?? "", phoneDigits(phone));
                update({ phone, phoneSentAt: Date.now(), step: "phone-code" });
              })
            }
          />
        </Frame>
      );
    case "phone-code":
      return (
        <Frame step={2} title="휴대폰 인증" description={phoneDescription(state.type)}>
          <CodeVerify
            kind="phone"
            target={formatPhone(state.phone)}
            sentAt={state.phoneSentAt ?? 0}
            onEdit={() => update({ step: "phone" })}
            onResend={() => guard(() => signupApi.sendPhoneCode(state.signupToken ?? "", phoneDigits(state.phone)))}
            onVerify={(code) =>
              guard(async () => {
                await signupApi.verifyPhoneCode(state.signupToken ?? "", code);
                update({ step: "info" });
              })
            }
          />
        </Frame>
      );
    case "info":
      return (
        <InfoStep
          state={state}
          onExpired={() => setExpired(true)}
          onDone={(approved) => {
            const email = state.email;
            reset();
            setDone({ type: state.type, approved, email });
          }}
          onPhoneRequired={() => update({ step: "phone" })}
        />
      );
  }
}

function phoneDescription(type: SignupType): string {
  return type === "STUDENT"
    ? "명단과 같은 휴대폰 번호면 가입이 바로 승인돼요."
    : "계약서와 같은 휴대폰 번호면 가입이 바로 승인돼요.";
}

/** 단계 공통 틀: (뒤로) → 단계 표시 → 제목·설명 → 내용 */
function Frame({
  step,
  title,
  description,
  back,
  children,
}: {
  step: number;
  title: string;
  description: string;
  back?: { label: string; onClick: () => void } | { label: string; to: "/login" };
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-6">
      {back ? (
        "to" in back ? (
          <Link to={back.to} className={BACK_CLASS}>
            <ArrowLeft aria-hidden className="size-4" />
            {back.label}
          </Link>
        ) : (
          <button type="button" onClick={back.onClick} className={BACK_CLASS}>
            <ArrowLeft aria-hidden className="size-4" />
            {back.label}
          </button>
        )
      ) : null}
      <Stepper steps={STEPS} current={step} />
      <div className="flex flex-col gap-2">
        <h1 className="text-h2 text-foreground">{title}</h1>
        <p className="text-body-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  );
}

const BACK_CLASS =
  "inline-flex items-center gap-1.5 self-start text-body-sm text-muted-foreground hover:text-foreground";

const TYPES: { value: SignupType; title: string; description: string; icon: typeof BookOpen }[] = [
  { value: "STUDENT", title: "수강생", description: "수강 중인 과정의 기수로 가입해요", icon: BookOpen },
  { value: "MENTOR", title: "멘토", description: "오즈코딩스쿨과 계약한 멘토로 가입해요", icon: Users },
];

function TypeStep({ value, onNext }: { value: SignupType; onNext: (type: SignupType) => void }) {
  const [type, setType] = useState<SignupType>(value);
  return (
    <Frame
      step={0}
      title="회원가입"
      description="어떤 역할로 가입하시나요?"
      back={{ label: "로그인으로 돌아가기", to: "/login" }}
    >
      <div role="radiogroup" aria-label="가입 유형" className="grid gap-3 md:grid-cols-2">
        {TYPES.map((option) => {
          const checked = option.value === type;
          const Icon = option.icon;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={checked}
              onClick={() => setType(option.value)}
              className={cn(
                "flex flex-col gap-3 rounded-xl border p-4 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                checked ? "border-2 border-primary bg-accent" : "border-border bg-card hover:bg-accent/50",
              )}
            >
              <span className="flex items-center justify-between">
                <span
                  className={cn(
                    "inline-flex size-9 items-center justify-center rounded-lg",
                    checked ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
                  )}
                >
                  <Icon aria-hidden className="size-5" />
                </span>
                <span
                  aria-hidden
                  className={cn(
                    "inline-flex size-4 items-center justify-center rounded-full border",
                    checked ? "border-primary" : "border-input",
                  )}
                >
                  {checked ? <span className="size-2 rounded-full bg-primary" /> : null}
                </span>
              </span>
              <span className="flex flex-col gap-1">
                <span className="text-body-strong text-foreground">{option.title}</span>
                <span className="text-caption text-muted-foreground">{option.description}</span>
              </span>
            </button>
          );
        })}
      </div>
      <Button className="w-full" onClick={() => onNext(type)}>
        다음
      </Button>
      <p className="text-center text-body-sm text-muted-foreground">
        이미 계정이 있나요?{" "}
        <Link to="/login" className="text-body-strong text-primary-text hover:underline">
          로그인
        </Link>
      </p>
    </Frame>
  );
}

const emailForm = z.object({ email: emailSchema });

function EmailEntry({ type, initial, onSent }: { type: SignupType; initial: string; onSent: (email: string) => void }) {
  const [alert, setAlert] = useState<{ title: string; description?: string; until: Date } | null>(null);
  const [registered, setRegistered] = useState<string | null>(null);
  const blockedFor = useCountdown(alert ? alert.until.getTime() : null);
  const form = useForm<z.infer<typeof emailForm>>({
    resolver: zodResolver(emailForm),
    defaultValues: { email: initial },
  });
  const onSubmit = form.handleSubmit(async ({ email }) => {
    setAlert(null);
    setRegistered(null);
    try {
      await signupApi.sendEmailCode(email);
      onSent(email);
    } catch (error) {
      const limited = rateLimitAlert(error);
      if (limited) {
        setAlert(limited);
        return;
      }
      if (error instanceof ApiError && error.code === "email_already_registered") {
        setRegistered(email);
        form.setError("email", { message: "이미 가입된 이메일이에요." });
        return;
      }
      if (error instanceof ApiError && error.status === 422) {
        form.setError("email", { message: error.fieldErrors.email ?? error.message });
        return;
      }
      throw error;
    }
  });
  const blocked = alert !== null && blockedFor > 0;
  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
      {alert && blocked ? <Alert variant="warning" title={alert.title} description={alert.description} /> : null}
      <FormField
        label="이메일"
        helper={
          type === "STUDENT" ? "수강생은 수강 신청 때 쓴 이메일을 권장해요." : "Gmail(@gmail.com) 주소로 가입해요."
        }
        error={form.formState.errors.email?.message}
      >
        {(field) => (
          <div className="relative">
            <InputIcon icon={Mail} />
            <Input
              {...field}
              {...form.register("email")}
              type="email"
              autoComplete="email"
              placeholder="name@gmail.com"
              className="pl-9"
            />
          </div>
        )}
      </FormField>
      <Button type="submit" disabled={blocked || form.formState.isSubmitting} className="w-full">
        인증코드 받기
      </Button>
      {registered ? (
        <p className="-mt-2 text-center text-body-sm">
          <Link
            to="/login"
            search={{ email: registered }}
            className="text-body-strong text-primary-text hover:underline"
          >
            로그인하기
          </Link>
          <span className="mx-2 text-muted-foreground">·</span>
          <Link to="/password-reset" className="text-body-strong text-primary-text hover:underline">
            비밀번호 재설정
          </Link>
        </p>
      ) : null}
    </form>
  );
}

const phoneForm = z.object({
  phone: z.string().refine(isValidPhone, "010으로 시작하는 휴대폰 번호를 입력해 주세요."),
});

function PhoneEntry({ initial, onSend }: { initial: string; onSend: (phone: string) => Promise<void> }) {
  const [alert, setAlert] = useState<{ title: string; description?: string; until: Date } | null>(null);
  const blockedFor = useCountdown(alert ? alert.until.getTime() : null);
  const form = useForm<z.infer<typeof phoneForm>>({
    resolver: zodResolver(phoneForm),
    defaultValues: { phone: formatPhone(initial) },
  });
  const onSubmit = form.handleSubmit(async ({ phone }) => {
    setAlert(null);
    try {
      await onSend(phone);
    } catch (error) {
      const limited = rateLimitAlert(error);
      if (limited) {
        setAlert(limited);
        return;
      }
      if (error instanceof ApiError && (error.code === "phone_already_registered" || error.status === 422)) {
        form.setError("phone", {
          message: error.code === "phone_already_registered" ? "다른 계정에 등록된 휴대폰 번호예요." : error.message,
        });
        return;
      }
      throw error;
    }
  });
  const blocked = alert !== null && blockedFor > 0;
  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
      {alert && blocked ? <Alert variant="warning" title={alert.title} description={alert.description} /> : null}
      <FormField label="휴대폰 번호" error={form.formState.errors.phone?.message}>
        {(field) => (
          <Controller
            control={form.control}
            name="phone"
            render={({ field: control }) => (
              <div className="relative">
                <InputIcon icon={Smartphone} />
                <Input
                  {...field}
                  ref={control.ref}
                  name={control.name}
                  value={control.value}
                  onBlur={control.onBlur}
                  onChange={(event) => control.onChange(formatPhone(event.target.value))}
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel"
                  placeholder="010-1234-5678"
                  className="pl-9"
                />
              </div>
            )}
          />
        )}
      </FormField>
      <Button type="submit" disabled={blocked || form.formState.isSubmitting} className="w-full">
        인증코드 받기
      </Button>
    </form>
  );
}

const infoSchema = z
  .object({
    name: z.string().trim().min(1, "이름을 입력해 주세요.").max(50, "이름은 50자 이내로 입력해 주세요."),
    cohort_id: z.string().optional(),
    nickname: z.string().trim().max(30, "닉네임은 30자 이내로 입력해 주세요.").optional(),
    display_name_preference: z.enum(["NAME", "NICKNAME"]),
    password: passwordSchema,
    confirm: z.string(),
    type: z.enum(["STUDENT", "MENTOR"]),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "비밀번호가 서로 달라요." })
  .refine((v) => v.type !== "STUDENT" || Boolean(v.cohort_id), {
    path: ["cohort_id"],
    message: "신청 기수를 골라 주세요.",
  })
  .refine((v) => v.type !== "MENTOR" || v.display_name_preference === "NAME" || Boolean(v.nickname), {
    path: ["nickname"],
    message: "닉네임을 보이게 하려면 닉네임을 입력해 주세요.",
  });
type InfoValues = z.infer<typeof infoSchema>;

function InfoStep({
  state,
  onDone,
  onExpired,
  onPhoneRequired,
}: {
  state: SignupState;
  onDone: (approved: boolean) => void;
  onExpired: () => void;
  onPhoneRequired: () => void;
}) {
  const student = state.type === "STUDENT";
  const cohorts = useQuery({ ...signupCohortsQuery, enabled: student });
  const [error, setError] = useState<string | null>(null);
  const form = useForm<InfoValues>({
    resolver: zodResolver(infoSchema),
    mode: "onChange",
    defaultValues: {
      name: "",
      nickname: "",
      display_name_preference: "NAME",
      password: "",
      confirm: "",
      type: state.type,
    },
  });
  const [password, name, nickname] = useWatch({ control: form.control, name: ["password", "name", "nickname"] });
  const { errors, isValid, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await unwrap(
        api.POST("/api/v1/auth/signup", {
          body: {
            signup_token: state.signupToken ?? "",
            signup_type: state.type,
            name: values.name,
            password: values.password,
            ...(student
              ? { cohort_id: values.cohort_id ?? null }
              : { nickname: values.nickname || null, display_name_preference: values.display_name_preference }),
          },
        }),
      );
      onDone(result.approval_status === "APPROVED");
    } catch (err) {
      if (isSessionExpired(err)) return onExpired();
      if (err instanceof ApiError) {
        if (err.code === "phone_verification_required") return onPhoneRequired();
        if (err.code === "invalid_cohort")
          return form.setError("cohort_id", { message: "가입할 수 있는 기수를 골라 주세요." });
        if (err.code === "invalid_password") return form.setError("password", { message: err.message });
        for (const [field, message] of Object.entries(err.fieldErrors)) {
          form.setError(field as keyof InfoValues, { message });
        }
        setError(err.message);
        return;
      }
      setError("잠시 후 다시 시도해 주세요.");
    }
  });

  return (
    <Frame
      step={3}
      title="가입 정보"
      description={
        student
          ? "신청 기수 명단과 이름·휴대폰이 같으면 바로 승인돼요."
          : "계약서의 이름·휴대폰과 같으면 바로 승인돼요."
      }
    >
      {error ? <Alert variant="error" title="가입하지 못했어요" description={error} /> : null}
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <FormField
            label={student ? "이름" : "이름 (실명)"}
            helper={student ? "명단에 등록된 이름과 같게 입력하세요." : undefined}
            error={errors.name?.message}
          >
            {(field) => <Input {...field} {...form.register("name")} autoComplete="name" maxLength={50} />}
          </FormField>
          {student ? (
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
                        {(cohorts.data ?? []).map((c) => (
                          <SelectItem key={c.cohort_id} value={c.cohort_id}>
                            {c.bootcamp_name} {c.cohort_number}기 ({formatKst(c.start_date, "MM/dd")} ~{" "}
                            {formatKst(c.end_date, "MM/dd")})
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
              <FormField label="닉네임 (선택)" error={errors.nickname?.message}>
                {(field) => <Input {...field} {...form.register("nickname")} maxLength={30} placeholder="30자 이내" />}
              </FormField>
              <div className="flex flex-col gap-2">
                <span id="display-name-label" className="text-label text-foreground">
                  수강생에게 보일 이름
                </span>
                <Controller
                  control={form.control}
                  name="display_name_preference"
                  render={({ field }) => (
                    <RadioGroup
                      aria-labelledby="display-name-label"
                      value={field.value}
                      onValueChange={(v) => {
                        field.onChange(v);
                        void form.trigger("nickname");
                      }}
                    >
                      <RadioGroupItem value="NAME">{`실명${name ? ` (${name})` : ""}`}</RadioGroupItem>
                      <RadioGroupItem value="NICKNAME">{`닉네임${nickname ? ` (${nickname})` : ""}`}</RadioGroupItem>
                    </RadioGroup>
                  )}
                />
              </div>
            </>
          )}
          <FormField label="비밀번호" error={undefined}>
            {(field) => <PasswordInput {...field} {...form.register("password")} autoComplete="new-password" />}
          </FormField>
          <ul aria-label="비밀번호 규칙" className="flex flex-col gap-1">
            {PASSWORD_RULES.map((rule) => {
              const ok = rule.test(password);
              const Icon = ok ? CircleCheck : CircleX;
              return (
                <li
                  key={rule.id}
                  className={cn(
                    "flex items-center gap-2 text-caption",
                    ok ? "text-success-text" : "text-muted-foreground",
                  )}
                >
                  <Icon aria-hidden className="size-4" />
                  {rule.label}
                  <span className="sr-only">{ok ? " (충족)" : " (미충족)"}</span>
                </li>
              );
            })}
          </ul>
          <FormField label="비밀번호 확인" error={errors.confirm?.message}>
            {(field) => (
              <PasswordInput
                {...field}
                {...form.register("confirm", { deps: ["password"] })}
                autoComplete="new-password"
              />
            )}
          </FormField>
        </div>
        <Button type="submit" disabled={!isValid || isSubmitting} className="w-full">
          가입 신청
        </Button>
      </form>
    </Frame>
  );
}

/** 완료 (Figma `완료 · 승인 대기`·`완료 · 승인`). 로그인 화면에 가입한 이메일을 채운다 (F24). */
function SignupDone({ type, approved, email }: Done) {
  const source = type === "STUDENT" ? "명단" : "계약 정보";
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <span
        className={cn(
          "inline-flex size-14 items-center justify-center rounded-full",
          approved ? "bg-success-subtle text-success-text" : "bg-accent text-primary-text",
        )}
      >
        {approved ? <CircleCheck aria-hidden className="size-6" /> : <Hourglass aria-hidden className="size-6" />}
      </span>
      <div className="flex flex-col gap-2">
        <h1 className="text-h2 text-foreground">{approved ? "가입이 완료됐어요" : "가입 신청을 받았어요"}</h1>
        <p className="text-body-sm text-muted-foreground">
          {approved
            ? `${source}과 정보가 일치해 바로 승인됐어요. 다시 로그인하면 바로 이용할 수 있어요.`
            : `${source}에서 일치하는 정보를 찾지 못해 운영진이 확인하고 있어요. 승인되면 메일로 알려 드려요. 로그인하면 진행 상태를 볼 수 있어요.`}
        </p>
      </div>
      <Button asChild className="w-full">
        <Link to="/login" search={{ email }}>
          로그인하기
        </Link>
      </Button>
    </div>
  );
}
