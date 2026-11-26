import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { GraduationCap } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { bootcampsQuery, cohortsQuery, type Bootcamp, type Cohort } from "../api";
import { COHORT_STATUS, hrdLabel, periodLabel } from "../labels";
import { BootcampSheet } from "./bootcamp-sheet";
import { CohortSheet } from "./cohort-sheet";

export interface BootcampsSearch {
  bootcamp?: string;
  cohort?: string;
  panel?: "bootcamp";
}

const COLUMNS = "grid grid-cols-[52px_180px_84px_220px_minmax(0,1fr)] items-center gap-3";

/** 학사 > 과정·기수 (F74): 왼쪽 과정 목록 · 오른쪽 그 과정의 기수 표 */
export function BootcampsPage({ search }: { search: BootcampsSearch }) {
  const navigate = useNavigate();
  const bootcamps = useQuery(bootcampsQuery);
  const access = useQuery(staffAccessQuery);
  // 사용 중인 과정 먼저, 그다음 이름순(서버 순서)
  const ordered = [...(bootcamps.data ?? [])].sort((a, b) => Number(b.is_active) - Number(a.is_active));
  const selected = ordered.find((b) => b.id === search.bootcamp) ?? ordered[0];
  const go = (next: BootcampsSearch) => void navigate({ to: "/admin/academy/bootcamps", search: next });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">과정·기수</h1>
        <p className="text-body text-muted-foreground">
          Airtable에서 동기화된 과정과 기수예요. 운영에 필요한 항목만 고칠 수 있어요.
        </p>
      </div>
      {bootcamps.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : bootcamps.isError ? (
        <ErrorState onRetry={() => void bootcamps.refetch()} />
      ) : !selected ? (
        <EmptyState icon={GraduationCap} title="과정이 없어요" description="명단 동기화가 과정을 만들어요." />
      ) : (
        <div className="grid grid-cols-[280px_minmax(0,1fr)] items-start gap-6">
          <nav aria-label="과정" className="flex flex-col gap-0.5 rounded-2xl border border-border bg-card shadow-sm p-2">
            <span className="px-2 py-1 text-caption text-muted-foreground">과정 {ordered.length}개</span>
            {ordered.map((b) => (
              <BootcampItem key={b.id} bootcamp={b} selected={b.id === selected.id} />
            ))}
          </nav>
          <CohortsPanel
            bootcamp={selected}
            selectedCohort={search.cohort}
            onBootcampInfo={() => go({ bootcamp: selected.id, panel: "bootcamp" })}
          />
        </div>
      )}
      {selected && search.panel === "bootcamp" && access.data ? (
        <BootcampSheet
          key={selected.id}
          bootcamp={selected}
          access={access.data}
          onClose={() => go({ bootcamp: selected.id })}
        />
      ) : null}
      {selected && search.cohort && access.data ? (
        <CohortSheet
          key={search.cohort}
          cohortId={search.cohort}
          bootcamp={selected}
          access={access.data}
          onClose={() => go({ bootcamp: selected.id })}
        />
      ) : null}
    </div>
  );
}

function BootcampItem({ bootcamp: b, selected }: { bootcamp: Bootcamp; selected: boolean }) {
  return (
    <Link
      to="/admin/academy/bootcamps"
      search={{ bootcamp: b.id }}
      aria-current={selected ? "page" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-lg px-3 py-2.5 outline-none hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring",
        selected && "bg-accent hover:bg-accent",
      )}
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className={cn("truncate text-body-strong", selected ? "text-primary-text" : "text-foreground")}>
          {b.name}
        </span>
        <span className="text-caption text-muted-foreground">{b.code}</span>
      </span>
      {b.is_active ? null : <Badge variant="secondary">사용 안 함</Badge>}
    </Link>
  );
}

function CohortsPanel({
  bootcamp,
  selectedCohort,
  onBootcampInfo,
}: {
  bootcamp: Bootcamp;
  selectedCohort: string | undefined;
  onBootcampInfo: () => void;
}) {
  const cohorts = useQuery(cohortsQuery(bootcamp.id));
  // 보관한 기수는 숨기고 최근 기수부터
  const visible = (cohorts.data ?? [])
    .filter((c) => c.status !== "ARCHIVED")
    .sort((a, b) => b.cohort_number - a.cohort_number);
  return (
    <section aria-label={bootcamp.name} className="flex min-w-0 flex-col gap-4">
      <div className="flex items-center gap-2">
        <h2 className="text-h2 text-foreground">{bootcamp.name}</h2>
        <span className="text-body text-muted-foreground">{bootcamp.code}</span>
        <Badge variant={bootcamp.is_active ? "success" : "secondary"}>
          {bootcamp.is_active ? "사용 중" : "사용 안 함"}
        </Badge>
        <div className="flex-1" />
        <Button variant="outline" size="sm" onClick={onBootcampInfo}>
          과정 정보
        </Button>
      </div>
      {cohorts.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : cohorts.isError ? (
        <ErrorState onRetry={() => void cohorts.refetch()} />
      ) : visible.length === 0 ? (
        <EmptyState icon={GraduationCap} title="기수가 없어요" />
      ) : (
        <div role="table" aria-label="기수" className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          <div role="row" className={cn(COLUMNS, "bg-muted px-4 py-2.5 text-caption text-muted-foreground")}>
            {["기수", "기간", "상태", "HRD 회차", "디스코드 서버"].map((h) => (
              <span key={h} role="columnheader">
                {h}
              </span>
            ))}
          </div>
          {visible.map((c) => (
            <CohortRow key={c.id} cohort={c} bootcampId={bootcamp.id} selected={c.id === selectedCohort} />
          ))}
        </div>
      )}
      <p className="text-caption text-muted-foreground">보관한 기수는 목록에서 숨겨요.</p>
    </section>
  );
}

function CohortRow({ cohort: c, bootcampId, selected }: { cohort: Cohort; bootcampId: string; selected: boolean }) {
  const status = COHORT_STATUS[c.status];
  return (
    <div
      role="row"
      aria-label={`${c.cohort_number}기`}
      className={cn(COLUMNS, "relative border-t border-border px-4 py-3 hover:bg-accent/60", selected && "bg-accent")}
    >
      <span role="cell">
        <Link
          to="/admin/academy/bootcamps"
          search={{ bootcamp: bootcampId, cohort: c.id }}
          className="text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
        >
          {c.cohort_number}기
        </Link>
      </span>
      <span role="cell" className="text-body text-foreground">
        {periodLabel(c.start_date, c.end_date)}
      </span>
      <span role="cell">
        <Badge variant={status.variant}>{status.label}</Badge>
      </span>
      <span role="cell" className="truncate text-body text-muted-foreground">
        {hrdLabel(c.hrd_net_id, c.hrd_cohort_number)}
      </span>
      <span role="cell" className="truncate text-body text-muted-foreground">
        {c.discord_guild_id ?? "—"}
      </span>
    </div>
  );
}
