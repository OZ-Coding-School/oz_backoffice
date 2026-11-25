import { Markdown } from "@/components/markdown";
import { expertiseChips, type MentorProfile } from "@/features/apply/api";
import { Chips, MentorAvatar } from "@/features/apply/components/mentor-step";
import { cn } from "@/lib/utils";

/** 수강생에게 보이는 모습 (F79): 사진·표시 이름·한 줄 소개·전문 분야 칩 + 소개(마크다운) */
export function MentorCardView({
  mentor,
  compact = false,
}: {
  mentor: Pick<MentorProfile, "display_name" | "headline" | "profile_image_url" | "expertise" | "introduction">;
  compact?: boolean;
}) {
  const chips = expertiseChips(mentor.expertise);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <MentorAvatar mentor={mentor} size={compact ? "lg" : "xl"} />
        <div className="flex min-w-0 flex-col gap-1">
          <span className={cn(compact ? "text-h3" : "text-h2", "text-foreground")}>{mentor.display_name}</span>
          {mentor.headline ? <span className="text-body text-foreground">{mentor.headline}</span> : null}
          {!compact && chips.length ? <Chips items={chips} /> : null}
        </div>
      </div>
      {compact && chips.length ? <Chips items={chips} /> : null}
      <div className={cn("flex flex-col gap-2", !compact && "border-t border-border pt-4")}>
        {!compact ? <h3 className="text-caption text-muted-foreground">소개</h3> : null}
        {mentor.introduction ? (
          <Markdown>{mentor.introduction}</Markdown>
        ) : (
          <p className="text-body text-muted-foreground">아직 소개를 적지 않았어요.</p>
        )}
      </div>
    </div>
  );
}
