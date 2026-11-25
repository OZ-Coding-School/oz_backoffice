import { Controller } from "react-hook-form";

import { FormField } from "@/components/form-field";
import { MarkdownEditor } from "@/components/markdown-editor";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Spinner } from "@/components/ui/spinner";

import type { MentorProfile } from "../api";
import { HEADLINE_MAX_LENGTH, INTRODUCTION_MAX_LENGTH, NICKNAME_MAX_LENGTH } from "../form";
import { PHOTO_TYPES } from "../image";
import type { ProfileEditor } from "../profile-editor";
import { ExpertiseInput } from "./expertise-input";

/** 사진·이름·닉네임·보일 이름·한 줄 소개·전문 분야·소개(마크다운) 입력 */
export function ProfileFields({ editor, profile }: { editor: ProfileEditor; profile: MentorProfile }) {
  const { form, values, photo, processing, fileRef, shownPhoto, displayName, onPick, onRemovePhoto } = editor;
  const errors = form.formState.errors;
  return (
    <>
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
            {photo.kind === "replace" ? " 저장하면 바뀌어요." : photo.kind === "remove" ? " 저장하면 지워져요." : ""}
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
        label="소개 (마크다운)"
        error={errors.introduction?.message}
        helper={`${(values.introduction ?? "").length.toLocaleString("ko-KR")} / ${INTRODUCTION_MAX_LENGTH.toLocaleString("ko-KR")}`}
      >
        {(p) => (
          <Controller
            control={form.control}
            name="introduction"
            render={({ field }) => (
              <MarkdownEditor
                id={p.id}
                label="소개 작성 방식"
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
                maxLength={INTRODUCTION_MAX_LENGTH}
                invalid={!!p["aria-invalid"]}
                describedBy={p["aria-describedby"]}
                placeholder={"## 이런 분께 추천해요\n- 마크다운으로 적을 수 있어요"}
              />
            )}
          />
        )}
      </FormField>
    </>
  );
}
