import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/error-state";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import type { MentorProfile } from "@/features/mentor-profile/api";
import { ProfileFields } from "@/features/mentor-profile/components/profile-fields";
import { bodyOf, joinExpertise } from "@/features/mentor-profile/form";
import { saveErrorText, useProfileEditor } from "@/features/mentor-profile/profile-editor";
import { AcceptingCard } from "@/features/mentor-schedule/components/accepting-card";
import { maskPhone } from "@/features/profile/mask";
import { formatKst } from "@/lib/datetime";

import { mentorProfileQuery, useSaveProfile, useSetAccepting, type MentorItem } from "../api";
import { MentorCardView } from "./mentor-card-view";

/** 프로필 탭 (F79): 왼쪽 수강생에게 보이는 모습(수정은 같은 자리) · 오른쪽 계정·신청 받기 */
export function ProfileTab({ mentor, canManage }: { mentor: MentorItem; canManage: boolean }) {
  const profile = useQuery(mentorProfileQuery(mentor.id));
  const [editing, setEditing] = useState(false);
  const accepting = useSetAccepting(mentor.id);
  if (profile.isPending)
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  if (profile.isError) return <ErrorState onRetry={() => void profile.refetch()} />;
  if (editing) return <ProfileEdit mentorId={mentor.id} profile={profile.data} onDone={() => setEditing(false)} />;
  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section
        aria-labelledby="student-view-title"
        className="flex flex-col gap-5 rounded-2xl border border-border bg-card shadow-sm p-6"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 id="student-view-title" className="text-h3 text-foreground">
            수강생에게 보이는 모습
          </h2>
          {canManage ? (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              프로필 수정
            </Button>
          ) : null}
        </div>
        <MentorCardView mentor={profile.data} />
      </section>
      <div className="flex flex-col gap-4">
        <section
          aria-labelledby="account-title"
          className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-5"
        >
          <h2 id="account-title" className="text-h3 text-foreground">
            계정
          </h2>
          {mentor.is_registered ? (
            <dl className="grid grid-cols-[56px_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-body">
              <dt className="text-muted-foreground">실명</dt>
              <dd className="text-foreground">{mentor.name}</dd>
              <dt className="text-muted-foreground">이메일</dt>
              <dd className="break-all text-foreground">{mentor.email ?? "—"}</dd>
              <dt className="text-muted-foreground">휴대폰</dt>
              <dd className="text-foreground">{maskPhone(mentor.phone_number) ?? "—"}</dd>
              <dt className="text-muted-foreground">가입</dt>
              <dd className="text-foreground">
                {mentor.created_at ? `${formatKst(mentor.created_at, "yyyy.MM.dd")} 승인` : "—"}
              </dd>
            </dl>
          ) : (
            <>
              <dl className="grid grid-cols-[56px_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-body">
                <dt className="text-muted-foreground">이름</dt>
                <dd className="text-foreground">{mentor.name}</dd>
                <dt className="text-muted-foreground">휴대폰</dt>
                <dd className="text-foreground">{maskPhone(mentor.phone_number) ?? "—"}</dd>
                <dt className="text-muted-foreground">가입</dt>
                <dd className="text-foreground">가입 전</dd>
              </dl>
              <p className="text-caption text-muted-foreground">
                계약의 이름·휴대폰으로 멘토 가입을 하면 이 멘토에 계정이 연결돼요.
              </p>
            </>
          )}
        </section>
        <AcceptingCard
          accepting={mentor.accepting_requests}
          setter={accepting}
          readOnly={!canManage || !mentor.is_registered}
          {...(mentor.is_registered ? {} : { description: "가입하고 활성화된 뒤에 켤 수 있어요." })}
        />
      </div>
    </div>
  );
}

/** 프로필 수정 (F79): 왼쪽 폼(FE-12b 편집 부품) · 오른쪽 미리보기. 저장 전 떠나면 확인 */
function ProfileEdit({ mentorId, profile, onDone }: { mentorId: string; profile: MentorProfile; onDone: () => void }) {
  const editor = useProfileEditor(profile);
  const { form, values, dirty, shownPhoto, displayName } = editor;
  const save = useSaveProfile(mentorId);
  const [error, setError] = useState<string | null>(null);
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await save.mutateAsync({ body: form.formState.isDirty ? bodyOf(v) : null, photo: editor.photo });
      editor.resetPhoto();
      toast.success("프로필을 저장했어요");
      onDone();
    } catch (e) {
      setError(saveErrorText(e));
    }
  });

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
      <form
        aria-label="프로필 수정"
        noValidate
        onSubmit={(e) => void onSubmit(e)}
        className="flex flex-col gap-5 rounded-2xl border border-border bg-card shadow-sm p-6"
      >
        <h2 className="text-h3 text-foreground">프로필 수정</h2>
        <ProfileFields editor={editor} profile={profile} />
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              editor.discard();
              onDone();
            }}
          >
            취소
          </Button>
          <Button type="submit" disabled={!dirty || save.isPending || editor.processing}>
            저장
          </Button>
        </div>
      </form>
      <section
        aria-labelledby="preview-title"
        className="sticky top-4 flex flex-col gap-4 rounded-2xl border border-border bg-card shadow-sm p-6"
      >
        <h2 id="preview-title" className="text-label text-muted-foreground">
          수강생에게 보이는 모습
        </h2>
        <MentorCardView
          compact
          mentor={{
            display_name: displayName,
            headline: values.headline?.trim() || null,
            profile_image_url: shownPhoto,
            expertise: values.expertise?.length ? joinExpertise(values.expertise) : null,
            introduction: values.introduction?.trim() || null,
          }}
        />
      </section>
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
