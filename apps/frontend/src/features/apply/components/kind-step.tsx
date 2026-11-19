import { useQuery } from "@tanstack/react-query";
import { User, Users } from "lucide-react";

import { formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { mentorsQuery } from "../api";
import type { ApplyGate, ApplyKind } from "../gate";

/**
 * 종류 선택 (Figma `Screen / 종류 선택`, F31): 1:1·팀을 모두 허용한 기수의 첫 화면.
 * 팀 카드는 팀에 속해 있을 때만 고를 수 있다. '대기 신청' 줄은 없다(F30·F31).
 */
export function KindStep({
  gate,
  selected,
  onSelect,
}: {
  gate: ApplyGate;
  selected: ApplyKind | null;
  onSelect: (kind: ApplyKind) => void;
}) {
  const cohortId = gate.cohort?.enrollment.cohort_id ?? "";
  const mentors = useQuery({ ...mentorsQuery(cohortId), enabled: !!cohortId });
  const team = gate.team;
  return (
    <div role="radiogroup" aria-label="멘토링 종류" className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <KindCard
        kind="team"
        title="팀 멘토링"
        description="팀원과 함께 담당 멘토에게 받아요"
        checked={selected === "team"}
        disabled={!team}
        onSelect={() => onSelect("team")}
        rows={
          team
            ? [
                ["팀", `${team.label} (${team.members.length}명)`],
                ["멘토", `${team.mentor.display_name} (담당, 자동 선택)`],
                ["남은 시간", `팀 계좌 ${formatMinutes(gate.teamAccount?.remaining_minutes ?? 0)}`],
              ]
            : [["팀", "아직 속한 팀이 없어요"]]
        }
      />
      <KindCard
        kind="one"
        title="1:1 멘토링"
        description="기수 멘토 중 원하는 멘토에게 받아요"
        checked={selected === "one"}
        onSelect={() => onSelect("one")}
        rows={[
          ["멘토", mentors.data ? `${mentors.data.length}명 중 선택` : "-"],
          ["남은 시간", `내 계좌 ${formatMinutes(gate.oneAccount?.remaining_minutes ?? 0)}`],
        ]}
      />
    </div>
  );
}

function KindCard({
  kind,
  title,
  description,
  checked,
  disabled,
  onSelect,
  rows,
}: {
  kind: ApplyKind;
  title: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onSelect: () => void;
  rows: [string, string][];
}) {
  const Icon = kind === "team" ? Users : User;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      aria-label={title}
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        "flex flex-col gap-4 rounded-xl border bg-card p-5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-60",
        checked ? "border-primary bg-accent ring-1 ring-primary" : "border-border",
      )}
    >
      <span className="flex items-start gap-3">
        <span
          aria-hidden
          className={cn(
            "inline-flex size-9 shrink-0 items-center justify-center rounded-lg",
            checked ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
          )}
        >
          <Icon className="size-4.5" />
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-h3 text-foreground">{title}</span>
          <span className="text-caption text-muted-foreground">{description}</span>
        </span>
        <span
          aria-hidden
          className={cn(
            "mt-1 inline-flex size-4 shrink-0 items-center justify-center rounded-full border",
            checked ? "border-primary" : "border-input",
          )}
        >
          {checked ? <span className="size-2 rounded-full bg-primary" /> : null}
        </span>
      </span>
      <dl className="flex flex-col gap-2 border-t border-border pt-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex gap-4">
            <dt className="w-18 shrink-0 text-caption text-muted-foreground">{label}</dt>
            <dd className="text-body text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </button>
  );
}
