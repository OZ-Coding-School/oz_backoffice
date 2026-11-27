import { useQuery } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { BookOpen, Check, ChevronDown, ChevronRight, Clock, Search } from "lucide-react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import type { CohortStatus } from "@/features/admin-academy/api";
import { COHORT_STATUS } from "@/features/admin-academy/labels";
import { cn } from "@/lib/utils";

import { staffAccessQuery, type StaffCohort } from "../api";
import { cohortIdOf, pickableCohorts, recentCohortIds, rememberCohort } from "../current-cohort";

/** 기본으로 보이는 상태: 진행 중·개강 전 (종료·비활성은 '종료된 기수도 보기') */
const OPEN: readonly string[] = ["ONGOING", "PLANNED"];

const nameOf = (c: StaffCohort) => `${c.bootcamp_name} ${c.cohort_number}기`;
const dot = (d: string) => d.replaceAll("-", ".").slice(2);

/** 과정 목록 (서버 순서 = 진행 중 먼저를 지킨다) */
function bootcampsOf(cohorts: StaffCohort[]): { id: string; name: string; cohorts: StaffCohort[] }[] {
  const groups = new Map<string, { id: string; name: string; cohorts: StaffCohort[] }>();
  for (const c of cohorts) {
    const g = groups.get(c.bootcamp_id) ?? { id: c.bootcamp_id, name: c.bootcamp_name, cohorts: [] };
    g.cohorts.push(c);
    groups.set(c.bootcamp_id, g);
  }
  return [...groups.values()];
}

/**
 * 상단 막대의 현재 기수 선택기 (F59·F90, 모양은 F94).
 * 왼쪽 과정 · 오른쪽 그 과정의 기수, 위에 검색과 최근 고른 기수. 기본은 진행 중·개강 전만.
 * 기수 단위 화면(`/admin/cohorts/{id}/…`)에서만 보이고, 고르면 같은 화면의 그 기수 주소로 간다.
 */
export function CohortPicker() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const access = useQuery(staffAccessQuery);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [showClosed, setShowClosed] = useState(false);
  const [bootcampId, setBootcampId] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const cohortId = cohortIdOf(pathname);
  const all = pickableCohorts(access.data?.cohorts ?? []);
  const current = all.find((c) => c.id === cohortId);

  // 주소로 들어와도 마지막으로 본 기수로 기억한다
  useEffect(() => {
    if (cohortId) rememberCohort(cohortId);
  }, [cohortId]);

  if (!cohortId) return null;
  const visible = showClosed ? all : all.filter((c) => OPEN.includes(c.status) || c.id === cohortId);
  const bootcamps = bootcampsOf(visible);
  const selectedBootcamp =
    bootcamps.find((b) => b.id === bootcampId) ?? bootcamps.find((b) => b.id === current?.bootcamp_id) ?? bootcamps[0];
  const term = q.trim();
  const words = term.split(/\s+/).filter(Boolean);
  const found = term ? all.filter((c) => words.every((w) => nameOf(c).includes(w))) : [];
  const recentCohorts = recent
    .map((id) => all.find((c) => c.id === id))
    .filter((c): c is StaffCohort => !!c && c.id !== cohortId);

  const pick = (c: StaffCohort) => {
    setOpen(false);
    setQ("");
    rememberCohort(c.id);
    void navigate({ to: pathname.replace(`/admin/cohorts/${cohortId}/`, `/admin/cohorts/${c.id}/`) });
  };
  const onOpenChange = (next: boolean) => {
    setOpen(next);
    if (next) {
      setRecent(recentCohortIds());
      setBootcampId(null);
    }
  };

  return (
    <>
      <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}>
        <PopoverPrimitive.Trigger
          aria-label="현재 기수"
          className="flex items-center gap-2.5 rounded-lg bg-sidebar-accent py-1.5 pr-2.5 pl-3 text-left text-sidebar-accent-foreground outline-none hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring"
        >
          <BookOpen aria-hidden className="size-4 shrink-0" />
          <span className="flex flex-col">
            <span className="text-caption">현재 기수</span>
            <span className="text-body-strong">{current ? nameOf(current) : "기수를 골라 주세요"}</span>
          </span>
          <ChevronDown aria-hidden className="size-4 shrink-0" />
        </PopoverPrimitive.Trigger>
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Content
            align="start"
            sideOffset={6}
            aria-label="기수 고르기"
            className="z-50 flex w-[36rem] flex-col overflow-hidden rounded-2xl border border-border bg-popover shadow-lg"
          >
            <div className="flex flex-col gap-2.5 border-b border-border p-3">
              <label className="flex items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-2 focus-within:ring-2 focus-within:ring-ring">
                <Search aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="과정·기수 검색 (예: 백엔드 12)"
                  aria-label="과정·기수 검색"
                  className="min-w-0 flex-1 bg-transparent text-body text-foreground outline-none placeholder:text-muted-foreground"
                />
              </label>
              {recentCohorts.length > 0 && !term ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
                    <Clock aria-hidden className="size-3.5" />
                    최근
                  </span>
                  {recentCohorts.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      aria-label={`최근 ${nameOf(c)}`}
                      onClick={() => pick(c)}
                      className="rounded-full border border-border px-2.5 py-0.5 text-caption text-foreground outline-none hover:border-primary/40 hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {nameOf(c)}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {term ? (
              <div className="flex max-h-80 flex-col overflow-y-auto p-2">
                {found.length === 0 ? (
                  <p className="px-2.5 py-6 text-center text-body-sm text-muted-foreground">맞는 기수가 없어요.</p>
                ) : (
                  found.map((c) => (
                    <CohortRow key={c.id} cohort={c} on={c.id === cohortId} label={nameOf(c)} onPick={pick} />
                  ))
                )}
              </div>
            ) : (
              <div className="grid h-80 grid-cols-[15rem_minmax(0,1fr)]">
                <ul aria-label="과정" className="flex flex-col overflow-y-auto border-r border-border bg-muted/40 p-2">
                  {bootcamps.map((b) => {
                    const on = b.id === selectedBootcamp?.id;
                    const ongoing = b.cohorts.filter((c) => c.status === "ONGOING").length;
                    return (
                      <li key={b.id}>
                        <button
                          type="button"
                          aria-pressed={on}
                          onClick={() => setBootcampId(b.id)}
                          className={cn(
                            "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            on
                              ? "bg-card text-body-strong text-foreground shadow-sm"
                              : "text-muted-foreground hover:bg-card/60 hover:text-foreground",
                          )}
                        >
                          <span className="min-w-0 flex-1 truncate">{b.name}</span>
                          {ongoing > 0 ? (
                            <span className="rounded-full bg-success-subtle px-1.5 text-caption-strong text-success-text">
                              {ongoing}
                            </span>
                          ) : null}
                          <ChevronRight aria-hidden className="size-3.5 shrink-0 opacity-50" />
                        </button>
                      </li>
                    );
                  })}
                </ul>
                <div
                  role="group"
                  aria-label={selectedBootcamp ? `${selectedBootcamp.name} 기수` : "기수"}
                  className="flex flex-col overflow-y-auto p-2"
                >
                  {selectedBootcamp ? (
                    selectedBootcamp.cohorts.map((c) => (
                      <CohortRow key={c.id} cohort={c} on={c.id === cohortId} label={nameOf(c)} onPick={pick} short />
                    ))
                  ) : (
                    <p className="px-2.5 py-6 text-center text-body-sm text-muted-foreground">
                      볼 수 있는 기수가 없어요.
                    </p>
                  )}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between border-t border-border px-3 py-2.5">
              <label className="inline-flex items-center gap-2 text-body-sm text-muted-foreground">
                <Switch checked={showClosed} onCheckedChange={setShowClosed} aria-label="종료된 기수도 보기" />
                종료된 기수도 보기
              </label>
              <span className="text-caption text-muted-foreground">
                {visible.length} / {all.length}개 기수
              </span>
            </div>
          </PopoverPrimitive.Content>
        </PopoverPrimitive.Portal>
      </PopoverPrimitive.Root>
      <span aria-hidden className="mx-2 h-6 w-px bg-border" />
    </>
  );
}

function CohortRow({
  cohort: c,
  on,
  label,
  short = false,
  onPick,
}: {
  cohort: StaffCohort;
  on: boolean;
  label: string;
  short?: boolean;
  onPick: (c: StaffCohort) => void;
}) {
  const status = COHORT_STATUS[c.status as CohortStatus] ?? COHORT_STATUS.ENDED;
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={label}
      onClick={() => onPick(c)}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
        on && "bg-sidebar-accent text-sidebar-accent-foreground hover:bg-sidebar-accent",
      )}
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className={cn("truncate text-body", on ? "text-body-strong" : "text-foreground")}>
          {short ? `${c.cohort_number}기` : label}
        </span>
        <span className="text-caption text-muted-foreground">
          {dot(c.start_date)} ~ {dot(c.end_date)}
        </span>
      </span>
      <Badge variant={status.variant}>{status.label}</Badge>
      {on ? <Check aria-hidden className="size-4" /> : null}
    </button>
  );
}
