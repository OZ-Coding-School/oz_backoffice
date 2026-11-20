import { useQuery } from "@tanstack/react-query";
import { BookOpen, CalendarDays, Lock, LogOut, Mail, ShieldCheck, User } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { meQuery } from "@/features/auth/api";
import { ROLE_LABELS } from "@/features/auth/messages";
import { activeCohort, cohortLabel, ENROLLMENT_STATUS_LABELS, enrollmentsQuery } from "@/features/member/api";
import { useLogout } from "@/features/member/logout";

import { passwordChangeQuery, useSendPasswordLink } from "../api";
import { maskPhone } from "../mask";
import { PasswordChangeDialog } from "./password-change-dialog";

/** 내 정보 (Figma `Column / 내 정보 (FE-6a)`, F37·A72) */
export function ProfilePage() {
  const me = useQuery(meQuery);
  const enrollments = useQuery(enrollmentsQuery);
  const password = useQuery(passwordChangeQuery);
  const send = useSendPasswordLink();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const user = me.data;
  if (!user) return null;
  const active = enrollments.data ? activeCohort(enrollments.data) : null;
  const e = active?.enrollment;
  const phone = maskPhone(user.phone_number);

  // 열 때 보낸 링크가 없으면 바로 보낸다. 이미 보냈거나 인증 중이면 그 상태로 연다 (A72)
  const openDialog = () => {
    setOpen(true);
    if ((password.data?.state ?? "NONE") === "NONE") send.mutate();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="flex flex-1 items-center gap-3">
          <span aria-hidden className="inline-flex size-8 items-center justify-center rounded-md bg-accent">
            <User className="size-4 text-primary-text" />
          </span>
          <div className="flex flex-col">
            <h1 className="text-h2 text-foreground">내 정보</h1>
            <p className="text-caption text-muted-foreground">로그인 계정과 수강 정보예요</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 md:flex">
          {password.data?.available ? (
            <Button variant="outline" size="sm" onClick={openDialog}>
              <Lock aria-hidden />
              비밀번호 재설정
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void logout()}
            className={password.data?.available ? undefined : "col-span-2"}
          >
            <LogOut aria-hidden />
            로그아웃
          </Button>
        </div>
      </div>
      <section aria-label="계정" className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex items-center gap-4 bg-muted/60 px-4 py-6 md:px-5">
          <Avatar name={user.name} className="size-14 text-h3" />
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-h2 text-foreground">{user.name}</span>
              <Badge variant="primary">{ROLE_LABELS[user.account_type] ?? user.account_type}</Badge>
              {user.approval_status === "APPROVED" ? <Badge variant="success">승인됨</Badge> : null}
            </div>
            {e ? (
              <p className="text-body text-muted-foreground">
                {cohortLabel(e)} · {ENROLLMENT_STATUS_LABELS[e.status]}
              </p>
            ) : null}
          </div>
        </div>
        <dl className="grid grid-cols-1 divide-y divide-border border-t border-border md:grid-cols-2 md:divide-y-0 lg:grid-cols-4">
          <Field icon={Mail} label="이메일" className="md:border-b lg:border-b-0">
            <span className="break-all">{user.email}</span>
          </Field>
          <Field icon={ShieldCheck} label="휴대폰" className="md:border-b md:border-l lg:border-b-0">
            {phone ? (
              <span className="inline-flex items-center gap-2">
                {phone}
                <Badge variant="secondary">인증됨</Badge>
              </span>
            ) : (
              "-"
            )}
          </Field>
          <Field icon={BookOpen} label="수강 과정" className="lg:border-l">
            {e ? cohortLabel(e) : "-"}
          </Field>
          <Field icon={CalendarDays} label="수강 기간" className="md:border-l">
            {e ? `${e.start_date.replaceAll("-", ".")} ~ ${e.end_date.replaceAll("-", ".")}` : "-"}
          </Field>
        </dl>
      </section>
      {open ? <PasswordChangeDialog email={user.email} open={open} onOpenChange={setOpen} /> : null}
    </div>
  );
}

function Field({
  icon: Icon,
  label,
  className,
  children,
}: {
  icon: typeof Mail;
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`flex flex-col gap-1 border-border px-4 py-3.5 md:px-5 ${className ?? ""}`}>
      <dt className="inline-flex items-center gap-1.5 text-caption text-muted-foreground">
        <Icon aria-hidden className="size-3.5" />
        {label}
      </dt>
      <dd className="text-body-strong text-foreground">{children}</dd>
    </div>
  );
}
