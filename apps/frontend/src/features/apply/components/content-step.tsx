import { Eye, Pencil } from "lucide-react";
import { useState } from "react";
import type { UseFormReturn } from "react-hook-form";
import { useWatch } from "react-hook-form";

import { Markdown } from "@/components/markdown";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import { DETAIL_MAX_LENGTH, TOPIC_MAX_LENGTH, type ContentForm } from "../schemas";

/**
 * ③ 신청 내용 (Figma `Screen / 1:1 신청 내용`, F4). 주제와 마크다운 상세 내용.
 * 태블릿 이상은 작성·미리보기를 나란히, 모바일은 [작성]·[미리보기] 탭.
 */
export function ContentStep({ form }: { form: UseFormReturn<ContentForm> }) {
  const [topic, detail] = useWatch({ control: form.control, name: ["topic", "detail"] });
  const [tab, setTab] = useState<"write" | "preview">("write");
  const errors = form.formState.errors;
  return (
    <section className="flex flex-col gap-5 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-6">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <label htmlFor="apply-topic" className="text-label text-foreground">
            주제
          </label>
          <span className="text-caption text-muted-foreground">
            {topic.length} / {TOPIC_MAX_LENGTH}
          </span>
        </div>
        <Input
          id="apply-topic"
          maxLength={TOPIC_MAX_LENGTH}
          placeholder="예: 포트폴리오 리뷰와 README 구성"
          aria-invalid={errors.topic ? true : undefined}
          {...form.register("topic")}
        />
        {errors.topic?.message ? <p className="text-caption text-destructive-text">{errors.topic.message}</p> : null}
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-label text-foreground" id="detail-label">
            상세 내용
          </span>
          <span className="text-caption text-muted-foreground">
            {detail.length.toLocaleString()} / {DETAIL_MAX_LENGTH.toLocaleString()}
          </span>
        </div>
        <div role="tablist" aria-label="상세 내용 보기" className="flex gap-1 md:hidden">
          {(["write", "preview"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={cn(
                "inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-label",
                tab === t ? "bg-accent text-accent-foreground" : "text-muted-foreground",
              )}
            >
              {t === "write" ? <Pencil aria-hidden className="size-3.5" /> : <Eye aria-hidden className="size-3.5" />}
              {t === "write" ? "작성" : "미리보기"}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-1 overflow-hidden rounded-lg border border-border md:grid-cols-2">
          <div className={cn("flex flex-col", tab === "preview" && "hidden md:flex")}>
            <p className="hidden items-center justify-between border-b border-border bg-muted px-3 py-2 text-label text-foreground md:flex">
              <span className="inline-flex items-center gap-1.5">
                <Pencil aria-hidden className="size-3.5" />
                작성
              </span>
              <span className="text-caption text-muted-foreground">마크다운</span>
            </p>
            <Textarea
              aria-labelledby="detail-label"
              aria-invalid={errors.detail ? true : undefined}
              maxLength={DETAIL_MAX_LENGTH}
              rows={12}
              className="min-h-72 rounded-none border-0 font-mono focus-visible:ring-0"
              placeholder={"## 질문하고 싶은 것\n- "}
              {...form.register("detail")}
            />
          </div>
          <div className={cn("flex flex-col border-border md:border-l", tab === "write" && "hidden md:flex")}>
            <p className="hidden items-center justify-between border-b border-border bg-accent px-3 py-2 text-label text-accent-foreground md:flex">
              <span className="inline-flex items-center gap-1.5">
                <Eye aria-hidden className="size-3.5" />
                미리보기
              </span>
              <span className="text-caption">멘토에게 보이는 모습</span>
            </p>
            <div aria-label="미리보기" className="min-h-72 px-4 py-3">
              {detail.trim() ? (
                <Markdown>{detail}</Markdown>
              ) : (
                <p className="text-body-sm text-muted-foreground">내용을 쓰면 여기에서 미리 볼 수 있어요.</p>
              )}
            </div>
          </div>
        </div>
        {errors.detail?.message ? <p className="text-caption text-destructive-text">{errors.detail.message}</p> : null}
        <p className="text-caption text-muted-foreground">
          마크다운을 쓸 수 있어요: 제목(##)·목록(-)·굵게(**)·링크·코드(```). 이미지와 HTML은 넣을 수 없어요
        </p>
      </div>
    </section>
  );
}
