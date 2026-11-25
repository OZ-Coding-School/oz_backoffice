import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { toast } from "sonner";

import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { errorText } from "@/features/admin-org/text";
import type { StaffAccess, StaffCohort } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";

import { studentKeys } from "../api";
import {
  syncKeys,
  syncRunQuery,
  syncRunsQuery,
  unmappedQuery,
  useStartSync,
  type SyncRun,
  type SyncTarget,
} from "../sync-api";

type Scope = SyncTarget["scope"];

const POLL_MS = 3000;
const POLL_LIMIT_MS = 5 * 60_000;
const REASONS: Record<string, string> = {
  cohort_not_found: "기수를 찾지 못함",
  cohort_changed: "다른 기수로 바뀜",
  invalid_name: "이름이 올바르지 않음",
  invalid_cohort_record: "기수 정보 없음",
};
const STATUS: Record<SyncRun["status"], { label: string; badge: "info" | "success" | "destructive" }> = {
  RUNNING: { label: "진행 중", badge: "info" },
  SUCCEEDED: { label: "성공", badge: "success" },
  FAILED: { label: "실패", badge: "destructive" },
};

/** 전체 범위 권한인가 (전체 동기화·매핑 실패 조회는 서버가 전체 범위만 허용) */
function isGlobal(access: StaffAccess, code: string): boolean {
  return access.is_super_admin || access.permissions.some((p) => p.code === code && p.is_global);
}

/** 실행 범위 문구: '전체' · '과정 · 백엔드 부트캠프' · '기수 · 백엔드 부트캠프 12기' */
function scopeLabel(run: SyncRun, cohorts: StaffCohort[]): string {
  if (run.scope_type === "ALL") return "전체";
  if (run.scope_type === "BOOTCAMP") {
    const c = cohorts.find((x) => x.bootcamp_id === run.bootcamp_id);
    return `과정 · ${c?.bootcamp_name ?? "—"}`;
  }
  const c = cohorts.find((x) => x.id === run.cohort_id);
  return `기수 · ${c ? `${c.bootcamp_name} ${c.cohort_number}기` : "—"}`;
}

function countsLabel(run: SyncRun): string {
  return [
    `가져옴 ${run.fetched_count.toLocaleString("ko-KR")}`,
    `반영 ${run.upserted_count.toLocaleString("ko-KR")}`,
    `빠짐 ${run.removed_count.toLocaleString("ko-KR")}`,
    `매핑 실패 ${run.unmapped_count.toLocaleString("ko-KR")}`,
  ].join(" · ");
}

/** 명단 동기화 패널 (F78): 지금 실행 · 실행 이력 · 매핑 실패 */
export function SyncSheet({
  access,
  cohorts,
  onClose,
}: {
  access: StaffAccess;
  cohorts: StaffCohort[];
  onClose: () => void;
}) {
  const canSync = access.is_super_admin || access.permissions.some((p) => p.code === "academy.roster.sync");
  const canSeeUnmapped = isGlobal(access, "academy.roster.read");
  const runs = useInfiniteQuery(syncRunsQuery);
  const unmapped = useQuery({ ...unmappedQuery, enabled: canSeeUnmapped });
  const items = runs.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead title="명단 동기화" description="Airtable 수강생 명단 · 매시간 자동" onClose={onClose} />
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
          {canSync ? <RunSection cohorts={cohorts} allowAll={isGlobal(access, "academy.roster.sync")} /> : null}
          <PanelSection title="실행 이력">
            {runs.isError ? (
              <Alert variant="error" title="실행 이력을 불러오지 못했어요." />
            ) : runs.isPending ? (
              <p className="text-body text-muted-foreground">불러오는 중…</p>
            ) : items.length === 0 ? (
              <p className="text-body text-muted-foreground">아직 실행한 동기화가 없어요.</p>
            ) : (
              <>
                <ul
                  aria-label="실행 이력"
                  className="divide-y divide-border overflow-hidden rounded-md border border-border"
                >
                  {items.map((run) => (
                    <li key={run.id} className="flex flex-col gap-1 px-3 py-2.5">
                      <span className="flex items-center gap-2">
                        <Badge variant={STATUS[run.status].badge}>{STATUS[run.status].label}</Badge>
                        <span className="min-w-0 flex-1 truncate text-body-strong text-foreground">
                          {scopeLabel(run, cohorts)} · {run.trigger === "SCHEDULED" ? "자동" : "수동"}
                        </span>
                        <span className="text-caption text-muted-foreground">
                          {formatKst(run.finished_at ?? run.started_at, "M/d HH:mm")}
                        </span>
                      </span>
                      <span className="text-caption text-muted-foreground">
                        {run.status === "FAILED"
                          ? (run.error_message ?? "실패했어요")
                          : run.status === "RUNNING"
                            ? "진행 중이에요"
                            : countsLabel(run)}
                      </span>
                    </li>
                  ))}
                </ul>
                {runs.hasNextPage ? (
                  <Button
                    variant="link"
                    size="sm"
                    className="self-start"
                    disabled={runs.isFetchingNextPage}
                    onClick={() => void runs.fetchNextPage()}
                  >
                    더 보기
                  </Button>
                ) : null}
              </>
            )}
          </PanelSection>
          {canSeeUnmapped ? (
            <PanelSection title={`매핑 실패 ${unmapped.data?.records.length ?? 0}건`}>
              {unmapped.isError ? (
                <Alert variant="error" title="매핑 실패 레코드를 불러오지 못했어요." />
              ) : !unmapped.data ? (
                <p className="text-body text-muted-foreground">불러오는 중…</p>
              ) : unmapped.data.records.length === 0 ? (
                <p className="text-body text-muted-foreground">매핑하지 못한 레코드가 없어요.</p>
              ) : (
                <>
                  <p className="text-caption text-muted-foreground">
                    가장 최근 전체 동기화
                    {unmapped.data.finished_at ? `(${formatKst(unmapped.data.finished_at, "M/d HH:mm")})` : ""}에서
                    처리하지 못한 레코드예요. Airtable에서 고친 뒤 다시 동기화해 주세요.
                  </p>
                  <ul
                    aria-label="매핑 실패"
                    className="divide-y divide-border overflow-hidden rounded-md border border-border"
                  >
                    {unmapped.data.records.map((r, i) => (
                      <li key={`${String(r.airtable_record_id)}-${i}`} className="flex items-center gap-2 px-3 py-2">
                        <span className="text-body-strong text-foreground">{String(r.name ?? "이름 없음")}</span>
                        <span className="text-caption text-muted-foreground">{String(r.cohort_label ?? "—")}</span>
                        <span className="flex-1" />
                        <span className="text-caption text-muted-foreground">
                          {REASONS[String(r.reason)] ?? String(r.reason)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </PanelSection>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** 지금 실행: 대상 유형 → (과정) → (기수) (F78) */
function RunSection({ cohorts, allowAll }: { cohorts: StaffCohort[]; allowAll: boolean }) {
  const id = useId();
  const client = useQueryClient();
  // 처음엔 아무것도 고르지 않고, 고른 유형에 필요한 선택지만 차례로 나타난다 (F78)
  const [scope, setScope] = useState<Scope | "">("");
  const [bootcampId, setBootcampId] = useState("");
  const [cohortId, setCohortId] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = useStartSync();
  const bootcamps = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of cohorts) if (!seen.has(c.bootcamp_id)) seen.set(c.bootcamp_id, c.bootcamp_name);
    return [...seen.entries()].map(([value, name]) => ({ value, name }));
  }, [cohorts]);
  const inBootcamp = cohorts
    .filter((c) => c.bootcamp_id === bootcampId)
    .sort((a, b) => b.cohort_number - a.cohort_number);

  /** 3초마다 실행 상태를 다시 읽는다 (최대 5분, F78). 끝나면 그 실행, 시간이 다 되면 null */
  const poll = async (target: string): Promise<SyncRun | null> => {
    const deadline = Date.now() + POLL_LIMIT_MS;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
      const current = await client.fetchQuery({ ...syncRunQuery(target), staleTime: 0 });
      if (current.status !== "RUNNING") return current;
    }
    return null;
  };

  const onRun = async () => {
    setError(null);
    if (!ready) return;
    const target: SyncTarget =
      scope === "ALL"
        ? { scope }
        : scope === "BOOTCAMP"
          ? { scope, id: bootcampId }
          : { scope: "COHORT", id: cohortId };
    try {
      const started = await start.mutateAsync(target);
      setRunId(started.id);
      toast.info("명단 동기화를 시작했어요");
      const done = await poll(started.id);
      if (!done) toast.info("동기화가 오래 걸리고 있어요. 실행 이력에서 결과를 확인해 주세요");
      else if (done.status === "SUCCEEDED") toast.success(`명단을 동기화했어요 (${countsLabel(done)})`);
      else toast.error(done.error_message ?? "명단 동기화에 실패했어요");
      void client.invalidateQueries({ queryKey: syncKeys.all });
      void client.invalidateQueries({ queryKey: studentKeys.all });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setRunId(null);
    }
  };
  const running = !!runId;
  const ready = scope === "ALL" || (scope === "BOOTCAMP" && !!bootcampId) || (scope === "COHORT" && !!cohortId);

  return (
    <PanelSection title="지금 실행">
      <PanelRow label="대상 유형" htmlFor={`${id}-scope`}>
        <Select
          value={scope}
          onValueChange={(v) => {
            setScope(v as Scope);
            setBootcampId("");
            setCohortId("");
          }}
        >
          <SelectTrigger id={`${id}-scope`} className="font-normal">
            <SelectValue placeholder="대상 유형을 고르세요" />
          </SelectTrigger>
          <SelectContent>
            {allowAll ? <SelectItem value="ALL">전체</SelectItem> : null}
            <SelectItem value="BOOTCAMP">과정</SelectItem>
            <SelectItem value="COHORT">기수</SelectItem>
          </SelectContent>
        </Select>
      </PanelRow>
      {scope === "BOOTCAMP" || scope === "COHORT" ? (
        <PanelRow label="과정" htmlFor={`${id}-bootcamp`}>
          <Select
            value={bootcampId}
            onValueChange={(v) => {
              setBootcampId(v);
              setCohortId("");
            }}
          >
            <SelectTrigger id={`${id}-bootcamp`} className="font-normal">
              <SelectValue placeholder="과정을 고르세요" />
            </SelectTrigger>
            <SelectContent>
              {bootcamps.map((b) => (
                <SelectItem key={b.value} value={b.value}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </PanelRow>
      ) : null}
      {scope === "COHORT" && bootcampId ? (
        <PanelRow label="기수" htmlFor={`${id}-cohort`}>
          <Select value={cohortId} onValueChange={setCohortId}>
            <SelectTrigger id={`${id}-cohort`} className="font-normal">
              <SelectValue placeholder="기수를 고르세요" />
            </SelectTrigger>
            <SelectContent>
              {inBootcamp.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.cohort_number}기
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </PanelRow>
      ) : null}
      {error ? <Alert variant="error" title={error} /> : null}
      <Button className="self-start" disabled={!ready || start.isPending || running} onClick={() => void onRun()}>
        {running ? "동기화 중…" : "동기화 실행"}
      </Button>
    </PanelSection>
  );
}
