import { useQuery } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { BookOpen, Check, ChevronDown, Search } from "lucide-react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { CohortStatus } from "@/features/admin-academy/api";
import { COHORT_STATUS } from "@/features/admin-academy/labels";
import { cn } from "@/lib/utils";

import { staffAccessQuery, type StaffCohort } from "../api";
import { cohortIdOf, pickableCohorts, rememberCohort } from "../current-cohort";

/** 과정별로 묶기 (서버 순서 = 진행 중 먼저를 지킨다) */
function groupByBootcamp(cohorts: StaffCohort[]): { name: string; cohorts: StaffCohort[] }[] {
  const groups = new Map<string, { name: string; cohorts: StaffCohort[] }>();
  for (const c of cohorts) {
    const group = groups.get(c.bootcamp_id) ?? { name: c.bootcamp_name, cohorts: [] };
    group.cohorts.push(c);
    groups.set(c.bootcamp_id, group);
  }
  return [...groups.values()];
}

/**
 * 상단 막대의 현재 기수 선택기 (Figma `현재 기수 선택 (FE-19a)`, F59·F90).
 * 기수 단위 화면(`/admin/cohorts/{id}/…`)에서만 보이고, 고르면 같은 화면의 그 기수 주소로 간다.
 */
export function CohortPicker() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const access = useQuery(staffAccessQuery);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const cohortId = cohortIdOf(pathname);
  const cohorts = pickableCohorts(access.data?.cohorts ?? []);
  const current = cohorts.find((c) => c.id === cohortId);

  // 주소로 들어와도 마지막으로 본 기수로 기억한다
  useEffect(() => {
    if (cohortId) rememberCohort(cohortId);
  }, [cohortId]);

  if (!cohortId) return null;
  const term = q.trim();
  const shown = term ? cohorts.filter((c) => `${c.bootcamp_name} ${c.cohort_number}기`.includes(term)) : cohorts;
  const pick = (c: StaffCohort) => {
    setOpen(false);
    setQ("");
    rememberCohort(c.id);
    void navigate({ to: pathname.replace(`/admin/cohorts/${cohortId}/`, `/admin/cohorts/${c.id}/`) });
  };

  return (
    <>
      <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
        <PopoverPrimitive.Trigger
          aria-label="현재 기수"
          className="flex items-center gap-2.5 rounded-lg bg-sidebar-accent py-1.5 pr-2.5 pl-3 text-left text-sidebar-accent-foreground outline-none hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring"
        >
          <BookOpen aria-hidden className="size-4 shrink-0" />
          <span className="flex flex-col">
            <span className="text-caption">현재 기수</span>
            <span className="text-body-strong">
              {current ? `${current.bootcamp_name} ${current.cohort_number}기` : "기수를 골라 주세요"}
            </span>
          </span>
          <ChevronDown aria-hidden className="size-4 shrink-0" />
        </PopoverPrimitive.Trigger>
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Content
            align="start"
            sideOffset={6}
            aria-label="기수 고르기"
            className="z-50 flex max-h-[70dvh] w-80 flex-col gap-1 overflow-hidden rounded-xl border border-border bg-popover p-2 shadow-lg"
          >
            <label className="flex items-center gap-2 rounded-lg border border-border px-2.5 py-2">
              <Search aria-hidden className="size-4 shrink-0 text-muted-foreground" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="과정·기수 검색"
                aria-label="과정·기수 검색"
                className="min-w-0 flex-1 bg-transparent text-body text-foreground outline-none placeholder:text-muted-foreground"
              />
            </label>
            <div className="flex flex-col overflow-y-auto">
              {shown.length === 0 ? (
                <p className="px-2.5 py-3 text-body-sm text-muted-foreground">맞는 기수가 없어요.</p>
              ) : (
                groupByBootcamp(shown).map((g) => (
                  <div key={g.name} role="group" aria-label={g.name} className="flex flex-col">
                    <p className="px-2.5 pt-2 pb-1 text-caption text-muted-foreground">{g.name}</p>
                    {g.cohorts.map((c) => {
                      const on = c.id === cohortId;
                      const status = COHORT_STATUS[c.status as CohortStatus] ?? COHORT_STATUS.ENDED;
                      return (
                        <button
                          key={c.id}
                          type="button"
                          aria-pressed={on}
                          aria-label={`${c.bootcamp_name} ${c.cohort_number}기`}
                          onClick={() => pick(c)}
                          className={cn(
                            "flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-body outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
                            on &&
                              "bg-sidebar-accent text-body-strong text-sidebar-accent-foreground hover:bg-sidebar-accent",
                          )}
                        >
                          <span className="flex-1">{c.cohort_number}기</span>
                          <Badge variant={status.variant}>{status.label}</Badge>
                          {on ? <Check aria-hidden className="size-4" /> : null}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </PopoverPrimitive.Content>
        </PopoverPrimitive.Portal>
      </PopoverPrimitive.Root>
      <span aria-hidden className="mx-2 h-6 w-px bg-border" />
    </>
  );
}
