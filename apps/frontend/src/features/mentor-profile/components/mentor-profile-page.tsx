import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { Eye, Lock, LogOut, User } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/error-state";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { MentorIntro } from "@/features/apply/components/mentor-dialog";
import { meQuery, type Me } from "@/features/auth/api";
import { useLogout } from "@/features/member/logout";
import { myAssignmentsQuery } from "@/features/mentor-requests/api";
import { passwordChangeQuery, useSendPasswordLink } from "@/features/profile/api";
import { PasswordChangeDialog } from "@/features/profile/components/password-change-dialog";
import { maskPhone } from "@/features/profile/mask";
import { cn } from "@/lib/utils";

import { mentorProfileQuery, useSaveMentorProfile, type MentorProfile, type PhotoChange } from "../api";
import {
  bodyOf,
  displayNameOf,
  formOf,
  HEADLINE_MAX_LENGTH,
  INTRODUCTION_MAX_LENGTH,
  joinExpertise,
  mentorProfileSchema,
  NICKNAME_MAX_LENGTH,
  type MentorProfileForm,
} from "../form";
import { photoProblem, PHOTO_TYPES, toProfilePhoto } from "../image";
import { assignmentPeriod, POLICY_LABELS, sortAssignments } from "../labels";
import { ExpertiseInput } from "./expertise-input";

const SAVE_ERRORS: Record<string, string> = {
  nickname_required: "닉네임으로 보이려면 닉네임을 적어 주세요.",
  invalid_nickname: "닉네임을 확인해 주세요.",
  invalid_headline: "한 줄 소개를 확인해 주세요.",
  invalid_expertise: "전문 분야를 확인해 주세요.",
  invalid_introduction: "소개를 확인해 주세요.",
  invalid_image: "사진을 올리지 못했어요. 다른 사진으로 다시 시도해 주세요.",
};

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

type Photo = PhotoChange & { preview?: string };

function ProfileEditor({ me, profile }: { me: Me; profile: MentorProfile }) {
  const form = useForm<MentorProfileForm>({ resolver: zodResolver(mentorProfileSchema), values: formOf(profile) });
  const save = useSaveMentorProfile();
  const [photo, setPhoto] = useState<Photo>({ kind: "keep" });
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const values = useWatch({ control: form.control }) as MentorProfileForm;
  const dirty = form.formState.isDirty || photo.kind !== "keep";

  // 미리 보기 주소는 바꾸거나 떠날 때 놓아 준다
  useEffect(() => () => (photo.preview ? URL.revokeObjectURL(photo.preview) : undefined), [photo.preview]);

  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });

  const shownPhoto =
    photo.kind === "replace" ? (photo.preview ?? null) : photo.kind === "remove" ? null : profile.profile_image_url;
  const displayName = displayNameOf(profile.name, values);

  const onPick = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const problem = photoProblem(file);
    if (problem) {
      toast.error(problem);
      return;
    }
    setProcessing(true);
    try {
      const image = await toProfilePhoto(file);
      setPhoto({ kind: "replace", image, preview: URL.createObjectURL(image) });
    } catch {
      toast.error("사진을 읽지 못했어요. 다른 사진을 골라 주세요.");
    } finally {
      setProcessing(false);
    }
  };

  const onRemovePhoto = () => setPhoto(profile.profile_image_url ? { kind: "remove" } : { kind: "keep" });

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await save.mutateAsync({ body: form.formState.isDirty ? bodyOf(v) : null, photo });
      setPhoto({ kind: "keep" });
      toast.success("프로필을 저장했어요");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setError((code && SAVE_ERRORS[code]) ?? "저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  });

  const errors = form.formState.errors;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start">
        <div className="flex flex-1 flex-col gap-1">
          <h1 className="text-h1 text-foreground">내 프로필</h1>
          <p className="text-body text-muted-foreground">수강생에게 보이는 정보예요.</p>
        </div>
        <Button variant="outline" onClick={() => setPreview(true)} className="max-md:w-full">
          <Eye aria-hidden />
          수강생에게 보이는 모습
        </Button>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-6">
        <form
          aria-label="프로필 편집"
          noValidate
          onSubmit={(e) => void onSubmit(e)}
          className="flex flex-col gap-5 rounded-xl border border-border bg-card p-4 md:p-6"
        >
          <div className="flex items-center gap-4">
            {shownPhoto ? (
              <img src={shownPhoto} alt="프로필 사진" className="size-14 shrink-0 rounded-full object-cover" />
            ) : (
              <Avatar name={displayName} className="size-14 text-h3" />
            )}
            <div className="flex flex-col gap-1.5">
              <span className="text-label text-foreground">프로필 사진</span>
              <span className="text-caption text-muted-foreground">
                PNG·JPEG·WebP, 정사각형으로 잘라 저장해요.
                {photo.kind === "replace"
                  ? " 저장하면 바뀌어요."
                  : photo.kind === "remove"
                    ? " 저장하면 지워져요."
                    : ""}
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={processing}
                  onClick={() => fileRef.current?.click()}
                >
                  {processing ? <Spinner className="size-4" /> : null}
                  사진 바꾸기
                </Button>
                {shownPhoto ? (
                  <Button type="button" variant="ghost" size="sm" onClick={onRemovePhoto}>
                    삭제
                  </Button>
                ) : null}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept={PHOTO_TYPES.join(",")}
                className="sr-only"
                tabIndex={-1}
                aria-label="프로필 사진 고르기"
                onChange={(e) => void onPick(e)}
              />
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label="이름 (실명)">{(p) => <Input {...p} value={profile.name} disabled />}</FormField>
            <FormField label="닉네임" error={errors.nickname?.message}>
              {(p) => <Input {...p} maxLength={NICKNAME_MAX_LENGTH} {...form.register("nickname")} />}
            </FormField>
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-label text-foreground">수강생에게 보일 이름</legend>
            <Controller
              control={form.control}
              name="preference"
              render={({ field }) => (
                <RadioGroup
                  value={field.value}
                  onValueChange={field.onChange}
                  aria-label="수강생에게 보일 이름"
                  className="flex-wrap gap-x-6 gap-y-2"
                >
                  <RadioGroupItem value="NAME">{`실명 (${profile.name})`}</RadioGroupItem>
                  <RadioGroupItem value="NICKNAME" disabled={!values.nickname?.trim()}>
                    {values.nickname?.trim() ? `닉네임 (${values.nickname.trim()})` : "닉네임 (먼저 적어 주세요)"}
                  </RadioGroupItem>
                </RadioGroup>
              )}
            />
          </fieldset>
          <FormField label="한 줄 소개" error={errors.headline?.message}>
            {(p) => (
              <Input
                {...p}
                maxLength={HEADLINE_MAX_LENGTH}
                placeholder="예: 네이버 백엔드 7년차 · 포트폴리오 리뷰"
                {...form.register("headline")}
              />
            )}
          </FormField>
          <FormField
            label="전문 분야"
            helper="Enter나 쉼표로 하나씩 넣어요"
            error={errors.expertise?.message ?? errors.expertise?.root?.message}
          >
            {(p) => (
              <Controller
                control={form.control}
                name="expertise"
                render={({ field }) => (
                  <ExpertiseInput
                    id={p.id}
                    value={field.value}
                    onChange={field.onChange}
                    invalid={!!p["aria-invalid"]}
                    describedBy={p["aria-describedby"]}
                  />
                )}
              />
            )}
          </FormField>
          <FormField
            label="소개"
            error={errors.introduction?.message}
            helper={`${(values.introduction ?? "").length.toLocaleString("ko-KR")} / ${INTRODUCTION_MAX_LENGTH.toLocaleString("ko-KR")}`}
          >
            {(p) => <Textarea {...p} rows={6} {...form.register("introduction")} />}
          </FormField>
          {error ? <Alert variant="error" title={error} /> : null}
          <div className="flex justify-end">
            <Button type="submit" disabled={!dirty || save.isPending || processing} className="max-md:w-full">
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
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5"
    >
      <h2 id="assignments-title" className="text-h3 text-foreground">
        배정된 기수
      </h2>
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
                  {assignmentPeriod(a)} · {POLICY_LABELS[a.cost_settlement_policy]}
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
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5"
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
