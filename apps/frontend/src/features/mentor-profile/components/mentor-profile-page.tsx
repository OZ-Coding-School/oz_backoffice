import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { Eye, Layers, Lock, LogOut, User } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CardTitle } from "@/components/section-card";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { MentorIntro } from "@/features/apply/components/mentor-dialog";
import { meQuery, type Me } from "@/features/auth/api";
import { useLogout } from "@/features/member/logout";
import { myAssignmentsQuery } from "@/features/mentor-requests/api";
import { passwordChangeQuery, useSendPasswordLink } from "@/features/profile/api";
import { PasswordChangeDialog } from "@/features/profile/components/password-change-dialog";
import { maskPhone } from "@/features/profile/mask";
import { cn } from "@/lib/utils";

import { mentorProfileQuery, useSaveMentorProfile, type MentorProfile } from "../api";
import { bodyOf, joinExpertise } from "../form";
import { assignmentPeriod, POLICY_LABELS, sortAssignments } from "../labels";
import { saveErrorText, useProfileEditor } from "../profile-editor";
import { ProfileFields } from "./profile-fields";

/** 멘토 내 프로필 (Figma `내 프로필 (FE-12b)`, F54·F56·A28). 데스크톱은 편집 | 배정 기수·계정 2단 */
export function MentorProfilePage() {
  const me = useQuery(meQuery);
  const profile = useQuery(mentorProfileQuery);
  if (profile.isPending || !me.data)
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  if (profile.isError) return <ErrorState onRetry={() => void profile.refetch()} />;
  return <ProfileEditor me={me.data} profile={profile.data} />;
}

function ProfileEditor({ me, profile }: { me: Me; profile: MentorProfile }) {
  const editor = useProfileEditor(profile);
  const { form, values, photo, dirty, shownPhoto, displayName } = editor;
  const save = useSaveMentorProfile();
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState(false);

  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await save.mutateAsync({ body: form.formState.isDirty ? bodyOf(v) : null, photo });
      editor.resetPhoto();
      toast.success("프로필을 저장했어요");
    } catch (e) {
      setError(saveErrorText(e));
    }
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={User}
        title="내 프로필"
        description="수강생에게 보이는 정보예요."
        actions={
          <Button variant="outline" onClick={() => setPreview(true)} className="max-md:w-full">
            <Eye aria-hidden />
            수강생에게 보이는 모습
          </Button>
        }
      />
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-6">
        <form
          aria-label="프로필 편집"
          noValidate
          onSubmit={(e) => void onSubmit(e)}
          className="flex flex-col gap-5 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-6"
        >
          <ProfileFields editor={editor} profile={profile} />
          {error ? <Alert variant="error" title={error} /> : null}
          <div className="flex justify-end">
            <Button type="submit" disabled={!dirty || save.isPending || editor.processing} className="max-md:w-full">
              저장
            </Button>
          </div>
        </form>
        <div className="flex flex-col gap-4 lg:gap-6">
          <AssignmentsCard />
          <AccountCard me={me} />
        </div>
      </div>
      <Dialog open={preview} onOpenChange={setPreview}>
        <DialogContent className="flex max-w-140 flex-col gap-4 p-6">
          <MentorIntro
            mentor={{
              display_name: displayName,
              headline: values.headline?.trim() || null,
              profile_image_url: shownPhoto,
              expertise: values.expertise?.length ? joinExpertise(values.expertise) : null,
              introduction: values.introduction?.trim() || null,
            }}
            badge={<p className="text-caption text-muted-foreground">저장하지 않은 내용도 함께 보여 줘요.</p>}
          />
          <div className="flex justify-end">
            <Button variant="ghost" onClick={() => setPreview(false)}>
              닫기
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={blocker.status === "blocked"} onOpenChange={(open) => (open ? undefined : blocker.reset?.())}>
        <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
          <DialogTitle className="text-h2 text-foreground">저장하지 않은 내용이 있어요</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            나가면 바꾼 내용이 사라져요. 나갈까요?
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => blocker.reset?.()}>
              머무르기
            </Button>
            <Button variant="destructive" onClick={() => blocker.proceed?.()}>
              나가기
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AssignmentsCard() {
  const assignments = useQuery(myAssignmentsQuery);
  const items = sortAssignments(assignments.data ?? []);
  return (
    <section
      aria-labelledby="assignments-title"
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
    >
      <CardTitle icon={Layers} id="assignments-title">
        배정된 기수
      </CardTitle>
      {assignments.isPending ? (
        <Spinner />
      ) : items.length === 0 ? (
        <p className="text-body text-muted-foreground">아직 배정된 기수가 없어요.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border border-t border-border">
          {items.map((a) => (
            <li key={a.id} className="flex items-center gap-3 py-3">
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className={cn("text-body-strong", a.is_active ? "text-foreground" : "text-muted-foreground")}>
                  {a.bootcamp_name} {a.cohort_number}기
                </span>
                <span className="text-caption text-muted-foreground">
                  {assignmentPeriod(a)}
                  {a.contract?.mentoring_time_basis ? ` · ${POLICY_LABELS[a.contract.mentoring_time_basis]}` : ""}
                </span>
              </div>
              <Badge variant={a.is_active ? "success" : "secondary"}>{a.is_active ? "활성" : "종료"}</Badge>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AccountCard({ me }: { me: Me }) {
  const password = useQuery(passwordChangeQuery);
  const send = useSendPasswordLink();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  // 열 때 보낸 링크가 없으면 바로 보낸다. 이미 보냈거나 인증 중이면 그 상태로 연다 (A72)
  const openDialog = () => {
    setOpen(true);
    if ((password.data?.state ?? "NONE") === "NONE") send.mutate();
  };
  return (
    <section
      aria-labelledby="account-title"
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
    >
      <h2 id="account-title" className="flex items-center gap-2 text-h3 text-foreground">
        <User aria-hidden className="size-4 text-muted-foreground" />
        계정
      </h2>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-2 text-body">
        <dt className="text-muted-foreground">이메일</dt>
        <dd className="break-all text-foreground">{me.email}</dd>
        <dt className="text-muted-foreground">휴대폰</dt>
        <dd className="text-foreground">{maskPhone(me.phone_number) ?? "-"}</dd>
      </dl>
      <div className="flex flex-wrap gap-2">
        {password.data?.available ? (
          <Button variant="outline" size="sm" onClick={openDialog}>
            <Lock aria-hidden />
            비밀번호 재설정
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" onClick={() => void logout()}>
          <LogOut aria-hidden />
          로그아웃
        </Button>
      </div>
      {open ? <PasswordChangeDialog email={me.email} open={open} onOpenChange={setOpen} /> : null}
    </section>
  );
}
