import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { STATUS } from "@/features/admin-contracts/labels";
import { cn } from "@/lib/utils";

import { contractCandidatesQuery, type AssignmentContract } from "../assignment-api";

const dot = (d: string) => d.replaceAll("-", ".");
const UNITS: Record<string, string> = { HOURLY: "시간당", PER_SESSION: "회당" };

function contractPeriod(c: AssignmentContract): string {
  if (!c.start_date && !c.end_date) return "기간 미정";
  return `${c.start_date ? dot(c.start_date) : ""} ~ ${c.end_date ? dot(c.end_date) : ""}`.trim();
}

/** 근거 계약 고르기 (F98): 후보를 라디오 카드로. 없으면 계약 화면으로 안내 */
export function ContractPicker({
  cohortId,
  mentorId,
  value,
  onChange,
}: {
  cohortId: string;
  mentorId: string;
  value: string;
  onChange: (contract: AssignmentContract) => void;
}) {
  const candidates = useQuery(contractCandidatesQuery(cohortId, mentorId));
  const items = candidates.data ?? [];
  const only = items.length === 1 ? items[0] : undefined;
  // 후보가 하나면 미리 고른다
  useEffect(() => {
    if (only && !value) onChange(only);
  }, [only, value, onChange]);
  if (candidates.isPending) return <Spinner />;
  if (items.length === 0)
    return (
      <div className="flex flex-col gap-1 rounded-xl border border-dashed border-border p-4 text-body font-normal">
        <span className="text-foreground">이 기수에 쓸 수 있는 계약이 없어요.</span>
        <span className="text-caption text-muted-foreground">
          이 멘토의 계약 완료·이행 중 계약 중 이 기수 계약이나 같은 과정의 공통 계약만 고를 수 있어요.
        </span>
        <Link
          to="/admin/administration/contracts"
          search={{ cohort: cohortId }}
          className="mt-1 text-caption-strong text-primary-text hover:underline"
        >
          행정 업무 › 계약에서 계약 만들기
        </Link>
      </div>
    );
  return (
    <ul role="radiogroup" aria-label="근거 계약" className="flex flex-col gap-2">
      {items.map((c) => {
        const on = c.id === value;
        const status = STATUS[c.status];
        return (
          <li key={c.id}>
            <button
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(c)}
              className={cn(
                "flex w-full items-start gap-3 rounded-xl border p-3 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                on ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border",
                  on ? "border-primary bg-primary text-primary-foreground" : "border-input",
                )}
              >
                {on ? <Check className="size-3" /> : null}
              </span>
              <span className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="flex flex-wrap items-center gap-1.5">
                  <span className="truncate text-body-strong text-foreground">{c.title}</span>
                  <Badge variant={status.badge}>{status.label}</Badge>
                  <Badge variant="outline">{c.cohort_id ? "기수 계약" : "과정 공통"}</Badge>
                </span>
                <span className="text-caption font-normal text-muted-foreground">
                  {contractPeriod(c)}
                  {c.unit_price != null
                    ? ` · ${UNITS[c.price_unit ?? ""] ?? ""} ${c.unit_price.toLocaleString("ko-KR")}원`
                    : ""}
                  {c.no_show_pay_amount ? ` · 노쇼 ${c.no_show_pay_amount.toLocaleString("ko-KR")}원` : ""}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
