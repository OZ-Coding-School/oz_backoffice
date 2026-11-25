import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { FileText } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Spinner } from "@/components/ui/spinner";
import { staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { hrdBootcampsQuery, type HrdBootcamp } from "../api";
import { TRAIN_TYPE_LABELS } from "../labels";
import { HrdCohortSheet } from "./hrd-cohort-sheet";
import { HrdSheet } from "./hrd-sheet";

export interface HrdSearch {
  hrd?: string;
  cohort?: string;
}

const COLUMNS = "grid grid-cols-[minmax(0,1.2fr)_190px_88px_64px_minmax(0,1.4fr)] items-center gap-3";

/** 학사 > HRD 과정 (F75): HRD 과정 표 + 슬라이드 패널(과정·회차) */
export function HrdPage({ search }: { search: HrdSearch }) {
  const navigate = useNavigate();
  const list = useQuery(hrdBootcampsQuery);
  const access = useQuery(staffAccessQuery);
  const items = list.data ?? [];
  const selected = items.find((h) => h.id === search.hrd);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">HRD 과정</h1>
        <p className="text-body text-muted-foreground">
          HRD-Net 훈련과정과 회차예요. 훈련과정 ID·회차 번호·기간은 Airtable 동기화가 정해요.
        </p>
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState icon={FileText} title="HRD 과정이 없어요" description="명단 동기화가 HRD 과정을 만들어요." />
      ) : (
        <div role="table" aria-label="HRD 과정" className="overflow-hidden rounded-xl border border-border bg-card">
          <div role="row" className={cn(COLUMNS, "bg-muted px-4 py-2.5 text-caption text-muted-foreground")}>
            {["HRD 과정", "훈련과정 ID", "훈련 유형", "회차", "연결 운영과정"].map((h) => (
              <span key={h} role="columnheader">
                {h}
              </span>
            ))}
          </div>
          {items.map((h) => (
            <HrdRow key={h.id} hrd={h} selected={h.id === search.hrd} />
          ))}
        </div>
      )}
      {selected && access.data ? (
        search.cohort ? (
          <HrdCohortSheet
            key={search.cohort}
            hrd={selected}
            cohortId={search.cohort}
            access={access.data}
            onClose={() => void navigate({ to: "/admin/academy/hrd", search: { hrd: selected.id } })}
          />
        ) : (
          <HrdSheet
            key={selected.id}
            hrd={selected}
            access={access.data}
            onClose={() => void navigate({ to: "/admin/academy/hrd", search: {} })}
          />
        )
      ) : null}
    </div>
  );
}

function HrdRow({ hrd: h, selected }: { hrd: HrdBootcamp; selected: boolean }) {
  return (
    <div
      role="row"
      aria-label={h.name}
      className={cn(COLUMNS, "relative border-t border-border px-4 py-3 hover:bg-accent/60", selected && "bg-accent")}
    >
      <span role="cell" className="min-w-0">
        <Link
          to="/admin/academy/hrd"
          search={{ hrd: h.id }}
          className="block truncate text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
        >
          {h.name}
        </Link>
      </span>
      <span role="cell" className="truncate text-body text-foreground">
        {h.hrd_net_id ?? "—"}
      </span>
      <span role="cell" className="text-body text-foreground">
        {h.train_type ? (TRAIN_TYPE_LABELS[h.train_type] ?? h.train_type) : "—"}
      </span>
      <span role="cell" className="text-body text-muted-foreground">
        {h.cohort_count}
      </span>
      <span role="cell" className="truncate text-body text-muted-foreground">
        {(h.bootcamps ?? []).map((b) => b.name).join(" · ") || "—"}
      </span>
    </div>
  );
}
