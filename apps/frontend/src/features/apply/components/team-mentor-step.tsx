import { useState } from "react";

import { Markdown } from "@/components/markdown";
import { Badge } from "@/components/ui/badge";
import { formatKst, formatMinutes } from "@/lib/datetime";

import { expertiseChips, type StudentTeam, type MentorProfile } from "../api";
import type { BalanceAccount } from "@/features/requests/api";
import { MentorDialog } from "./mentor-dialog";
import { Chips, MentorAvatar } from "./mentor-step";

/** 팀 담당 멘토 확인 (Figma `Screen / 팀 담당 멘토 확인`, F31). 담당 멘토가 자동으로 정해져 확인만 한다 */
export function TeamMentorStep({
  cohortId,
  team,
  mentor,
  account,
  myStudentId,
}: {
  cohortId: string;
  team: StudentTeam;
  mentor: MentorProfile | undefined;
  account: BalanceAccount | undefined;
  myStudentId: string | undefined;
}) {
  const [detail, setDetail] = useState(false);
  const chips = expertiseChips(mentor?.expertise);
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-5">
      <section className="flex min-w-0 flex-1 flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-5">
        <div className="flex items-start gap-3">
          <MentorAvatar mentor={mentor ?? { display_name: team.mentor.display_name, profile_image_url: null }} />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-h2 text-foreground">{team.mentor.display_name}</span>
              <Badge variant="primary">담당 멘토</Badge>
            </span>
            {mentor?.headline ? <span className="text-caption text-muted-foreground">{mentor.headline}</span> : null}
          </div>
          {mentor ? (
            <Badge variant={mentor.accepting_requests ? "success" : "secondary"}>
              {mentor.accepting_requests ? "신청 받는 중" : "신청 받지 않음"}
            </Badge>
          ) : null}
        </div>
        {chips.length ? <Chips items={chips} /> : null}
        {mentor?.introduction ? (
          <div className="line-clamp-3 overflow-hidden">
            <Markdown>{mentor.introduction}</Markdown>
          </div>
        ) : null}
        <button
          type="button"
          onClick={() => setDetail(true)}
          className="w-fit text-label text-primary-text underline-offset-4 hover:underline"
        >
          상세 소개 보기
        </button>
      </section>
      <aside className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card shadow-sm p-5 lg:w-85 lg:shrink-0">
        <h2 className="text-body-strong text-foreground">{team.label}</h2>
        <Row
          label="팀원"
          value={team.members.map((m) => (m.student_id === myStudentId ? `${m.name}(나)` : m.name)).join(", ")}
        />
        <Row
          label="팀 남은 시간"
          value={
            account
              ? `${formatMinutes(account.remaining_minutes)} · ${formatKst(`${account.valid_until}T12:00:00+09:00`, "MM/dd")}까지`
              : "지급된 시간이 없어요"
          }
        />
      </aside>
      <MentorDialog
        cohortId={cohortId}
        mentorId={detail ? team.mentor.mentor_id : null}
        onClose={() => setDetail(false)}
      />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-4">
      <span className="w-20 shrink-0 text-caption text-muted-foreground">{label}</span>
      <span className="min-w-0 text-body text-foreground">{value}</span>
    </div>
  );
}
