import { useQuery } from "@tanstack/react-query";
import { UserSearch } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Avatar } from "@/components/ui/avatar";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

import { expertiseChips, mentorsQuery, type MentorCard } from "../api";
import { MentorDialog } from "./mentor-dialog";

/** ① 멘토 선택 (Figma `Screen / 1:1 멘토 선택`). 신청 받는 멘토만, 이번 주 가능 시간은 없다(F28) */
export function MentorStep({
  cohortId,
  selected,
  onSelect,
}: {
  cohortId: string;
  selected: string | null;
  onSelect: (mentorId: string) => void;
}) {
  const mentors = useQuery(mentorsQuery(cohortId));
  const [detail, setDetail] = useState<string | null>(null);
  if (mentors.isPending) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (mentors.isError) return <ErrorState onRetry={() => void mentors.refetch()} />;
  if (mentors.data.length === 0) {
    return (
      <EmptyState
        icon={UserSearch}
        title="지금 신청을 받는 멘토가 없어요"
        description="멘토가 신청 받기를 켜면 여기에서 고를 수 있어요."
      />
    );
  }
  return (
    <>
      <div role="radiogroup" aria-label="멘토" className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {mentors.data.map((m) => (
          <MentorCard
            key={m.mentor_id}
            mentor={m}
            checked={m.mentor_id === selected}
            onSelect={() => onSelect(m.mentor_id)}
            onDetail={() => setDetail(m.mentor_id)}
          />
        ))}
      </div>
      <MentorDialog
        cohortId={cohortId}
        mentorId={detail}
        onClose={() => setDetail(null)}
        onSelect={(id) => {
          onSelect(id);
          setDetail(null);
        }}
      />
    </>
  );
}

function MentorCard({
  mentor,
  checked,
  onSelect,
  onDetail,
}: {
  mentor: MentorCard;
  checked: boolean;
  onSelect: () => void;
  onDetail: () => void;
}) {
  const chips = expertiseChips(mentor.expertise).slice(0, 3);
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-card p-4 transition-colors",
        checked ? "border-primary bg-accent ring-1 ring-primary" : "border-border",
      )}
    >
      <button
        type="button"
        role="radio"
        aria-checked={checked}
        onClick={onSelect}
        className="flex items-start gap-3 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <MentorAvatar mentor={mentor} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-body-strong text-foreground">{mentor.display_name}</span>
          {mentor.headline ? <span className="text-caption text-muted-foreground">{mentor.headline}</span> : null}
        </span>
        <span
          aria-hidden
          className={cn(
            "mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full border",
            checked ? "border-primary" : "border-input",
          )}
        >
          {checked ? <span className="size-2 rounded-full bg-primary" /> : null}
        </span>
      </button>
      {chips.length ? <Chips items={chips} /> : null}
      <button
        type="button"
        onClick={onDetail}
        className="w-fit text-label text-primary-text underline-offset-4 hover:underline"
      >
        상세 소개 보기
      </button>
    </div>
  );
}

export function MentorAvatar({
  mentor,
  size = "lg",
}: {
  mentor: Pick<MentorCard, "display_name" | "profile_image_url">;
  size?: "md" | "lg" | "xl";
}) {
  const box = size === "xl" ? "size-18 text-h2" : size === "lg" ? "size-10" : "size-8";
  return mentor.profile_image_url ? (
    <img
      src={mentor.profile_image_url}
      alt=""
      width={40}
      height={40}
      className={cn(box, "shrink-0 rounded-full object-cover")}
    />
  ) : (
    <Avatar name={mentor.display_name} className={box} />
  );
}

export function Chips({ items }: { items: readonly string[] }) {
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((c) => (
        <li
          key={c}
          className="rounded-full border border-border bg-background px-2.5 py-0.5 text-caption text-foreground"
        >
          {c}
        </li>
      ))}
    </ul>
  );
}
