import { useQuery } from "@tanstack/react-query";
import { useBlocker, useNavigate } from "@tanstack/react-router";
import { ChevronDown, ChevronRight, KeyRound } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { ApiError } from "@/api/errors";
import { CollapsibleGroup, GroupItem } from "@/components/collapsible-group";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { impactQuery } from "@/features/admin-org/api";
import { ImpactList } from "@/features/admin-org/components/impact-list";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import {
  permissionDefsQuery,
  positionsQuery,
  useSavePositionPermissions,
  type PermissionDef,
  type Position,
} from "../api";
import {
  assignmentScopeLabel,
  buildGroups,
  dataScopeLabel,
  diff,
  orderedCodes,
  positionLine,
  toggle,
  type EntityRow,
  type PermissionChange,
} from "../groups";

const ERRORS: Record<string, string> = {
  permission_requires_read: "관리·동작 권한은 조회와 함께 켜야 해요.",
  permission_not_found: "없는 권한이 있어요. 화면을 새로 고쳐 주세요.",
};

function errorText(e: unknown): string {
  if (e instanceof ApiError) return ERRORS[e.code] ?? e.message;
  return "저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
}

/**
 * 조직 설정 > 권한 (Figma `직위·권한 (FE-15d)`, F63·F65·A87): 왼쪽 직위 목록, 오른쪽 그 직위의 권한.
 * 좌우가 따로 스크롤하고, 저장 영역은 오른쪽 아래에 붙는다. 데스크톱만(F58)
 */
export function PermissionsPage({ positionId }: { positionId: string | undefined }) {
  const positions = useQuery(positionsQuery);
  const defs = useQuery(permissionDefsQuery);
  const access = useQuery(staffAccessQuery);
  const navigate = useNavigate();
  const canEdit = access.data ? hasPermission(access.data, "access.role.manage") : false;
  const list = positions.data ?? [];
  const selected = list.find((p) => p.id === positionId) ?? list[0];

  return (
    <div className="flex h-[calc(100dvh-10rem)] min-h-120 flex-col gap-6">
      <PageHeader
        icon={KeyRound}
        title="권한"
        description="직위마다 권한을 정해요. 직위가 곧 역할이고, 데이터 범위는 직위 설정과 담당 배정이 정해요."
      />
      {positions.isPending || defs.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : positions.isError || defs.isError ? (
        <ErrorState
          onRetry={() => {
            void positions.refetch();
            void defs.refetch();
          }}
        />
      ) : !selected ? (
        <EmptyState
          icon={KeyRound}
          title="아직 직위가 없어요"
          description="직위를 먼저 만들면 권한을 정할 수 있어요."
        />
      ) : (
        <div className="flex min-h-0 flex-1 gap-4">
          <nav
            aria-label="직위"
            className="flex w-72 shrink-0 flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
          >
            <div className="flex items-center gap-1.5 border-b border-border px-4 py-3">
              <span className="text-body-strong text-foreground">직위</span>
              <span className="text-caption text-muted-foreground">{list.length}</span>
            </div>
            <ul className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-2">
              {list.map((p) => {
                const active = p.id === selected.id;
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      aria-current={active ? "true" : undefined}
                      onClick={() => void navigate({ to: "/admin/org/permissions", search: { position: p.id } })}
                      className={cn(
                        "flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left",
                        active ? "bg-accent" : "hover:bg-muted",
                      )}
                    >
                      <span
                        className={cn(
                          "text-body",
                          active ? "font-semibold text-accent-foreground" : "font-medium text-foreground",
                        )}
                      >
                        {p.name}
                      </span>
                      <span className="text-caption text-muted-foreground">{positionLine(p)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
          <PositionPermissions key={selected.id} position={selected} defs={defs.data} canEdit={canEdit} />
        </div>
      )}
    </div>
  );
}

function PositionPermissions({
  position,
  defs,
  canEdit,
}: {
  position: Position;
  defs: PermissionDef[];
  canEdit: boolean;
}) {
  const groups = useMemo(() => buildGroups(defs), [defs]);
  const original = useMemo(() => new Set(position.permissions), [position.permissions]);
  const [draft, setDraft] = useState<Set<string>>(original);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const save = useSavePositionPermissions();
  const changes = diff(original, draft, defs);
  const dirty = changes.length > 0;

  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });

  const set = (def: PermissionDef, on: boolean) => setDraft((prev) => toggle(prev, def, on, defs));

  const onSave = async () => {
    try {
      await save.mutateAsync({ positionId: position.id, permissions: orderedCodes(draft, defs) });
      toast.success(`${position.name} 권한을 저장했어요`);
      setConfirming(false);
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  return (
    <section
      aria-label={`${position.name} 권한`}
      className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
    >
      <div className="flex flex-col gap-1 border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <h2 className="text-h2 text-foreground">{position.name}</h2>
          <Badge variant="outline">{assignmentScopeLabel(position.assignment_scope)}</Badge>
          <Badge variant="secondary">데이터 범위: {dataScopeLabel(position.data_scope)}</Badge>
        </div>
        <p className="text-body-sm text-muted-foreground">
          직원 {position.employee_count}명 · 최고 관리자는 직위와 상관없이 모든 권한을 가져요
        </p>
      </div>
      <div className="flex items-center gap-2 border-b border-border px-6 py-2.5">
        <span className="flex-1 text-caption text-muted-foreground">
          권한 그룹 {groups.length}개 · 켜진 권한 {draft.size}개
        </span>
        <Button size="sm" variant="ghost" onClick={() => setCollapsed(new Set())}>
          모두 펼치기
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setCollapsed(new Set(groups.map((g) => g.area)))}>
          모두 접기
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-4">
        {!canEdit ? (
          <Alert className="shrink-0" title="권한을 볼 수만 있어요. 바꾸려면 권한 관리 권한이 필요해요." />
        ) : null}
        {groups.map((group) => {
          const open = !collapsed.has(group.area);
          const on = group.codes.filter((c) => draft.has(c)).length;
          return (
            <div key={group.area} className="shrink-0 overflow-hidden rounded-lg border border-border">
              <div className="flex items-center gap-2 bg-muted px-3 py-2">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() =>
                    setCollapsed((prev) => {
                      const next = new Set(prev);
                      if (open) next.add(group.area);
                      else next.delete(group.area);
                      return next;
                    })
                  }
                  className="flex flex-1 items-center gap-2 text-left"
                >
                  {open ? (
                    <ChevronDown aria-hidden className="size-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight aria-hidden className="size-4 text-muted-foreground" />
                  )}
                  <span className="text-body-strong text-foreground">{group.area}</span>
                  <span className="text-caption text-muted-foreground">
                    {on} / {group.codes.length} 켜짐
                  </span>
                </button>
                {open ? (
                  <div aria-hidden className="flex text-caption text-muted-foreground">
                    <span className="w-24">조회</span>
                    <span className="w-24">관리·동작</span>
                  </div>
                ) : null}
              </div>
              {open ? (
                <ul>
                  {group.rows.map((row) => (
                    <EntityLine
                      key={row.entity}
                      row={row}
                      draft={draft}
                      original={original}
                      disabled={!canEdit || save.isPending}
                      onChange={set}
                    />
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>
      {canEdit ? (
        <div
          className={cn(
            "flex items-center gap-2 border-t border-border bg-card px-6 py-3",
            dirty && "shadow-[0_-4px_12px_rgb(0_0_0/0.06)]",
          )}
        >
          {dirty ? (
            <>
              <span aria-hidden className="size-2 rounded-full bg-warning" />
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="text-body-strong text-foreground">저장하지 않은 변경 {changes.length}개</span>
                <span className="truncate text-caption text-muted-foreground">
                  {changeSummary(changes)} — 저장하면 직원 {position.employee_count}명에게 바로 적용돼요
                </span>
              </div>
              <Button variant="outline" disabled={save.isPending} onClick={() => setDraft(original)}>
                변경 취소
              </Button>
              <Button disabled={save.isPending} onClick={() => setConfirming(true)}>
                저장
              </Button>
            </>
          ) : (
            <div className="flex flex-col">
              <span className="text-body-strong text-muted-foreground">변경 사항 없음</span>
              <span className="text-caption text-muted-foreground">
                권한을 바꾸면 여기에서 저장하거나 취소할 수 있어요.
              </span>
            </div>
          )}
        </div>
      ) : null}

      {confirming ? (
        <SaveDialog
          position={position}
          changes={changes}
          pending={save.isPending}
          onCancel={() => setConfirming(false)}
          onSave={() => void onSave()}
        />
      ) : null}

      <Dialog open={blocker.status === "blocked"} onOpenChange={(open) => (open ? undefined : blocker.reset?.())}>
        <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
          <DialogTitle className="text-h2 text-foreground">저장하지 않은 변경이 있어요</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            옮기면 바꾼 권한 {changes.length}개가 사라져요. {changeSummary(changes)}
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => blocker.reset?.()}>
              계속 고치기
            </Button>
            <Button variant="destructive" onClick={() => blocker.proceed?.()}>
              버리고 이동
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}

/**
 * 저장 확인 (F69): 위 '바뀐 권한'(추가·제거 상자), 아래 '영향받는 대상'(A93). 상자는 처음에 접어 둔다.
 */
function SaveDialog({
  position,
  changes,
  pending,
  onCancel,
  onSave,
}: {
  position: Position;
  changes: readonly PermissionChange[];
  pending: boolean;
  onCancel: () => void;
  onSave: () => void;
}) {
  const impact = useQuery(impactQuery("position", position.id));
  const added = changes.filter((c) => c.on);
  const removed = changes.filter((c) => !c.on);
  const affected = impact.data
    ? impact.data.employees.length + impact.data.registrations.filter((r) => r.status === "PENDING").length
    : 0;
  const mark = (on: boolean) => (
    <span
      aria-hidden
      className={cn(
        "inline-flex size-5 items-center justify-center rounded-sm text-caption-strong",
        on ? "bg-success-subtle text-success-text" : "bg-destructive-subtle text-destructive-text",
      )}
    >
      {on ? "+" : "−"}
    </span>
  );
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onCancel())}>
      <DialogContent className="flex max-w-150 flex-col gap-5 p-6">
        <div className="flex flex-col gap-1 pr-8">
          <DialogTitle className="text-h2 text-foreground">{position.name} 직위 권한 저장</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            바뀐 권한을 확인하고 저장하세요.
          </DialogDescription>
        </div>
        <section aria-labelledby="changed-title" className="flex flex-col gap-2">
          <h3 id="changed-title" className="flex items-baseline gap-1.5 text-body-strong text-foreground">
            바뀐 권한 <span className="text-caption text-muted-foreground">{changes.length}개</span>
          </h3>
          {added.length ? (
            <CollapsibleGroup title="추가된 권한" count={`${added.length}개`} leading={mark(true)}>
              {added.map((c) => (
                <GroupItem key={c.code} main={c.label} sub={c.area} />
              ))}
            </CollapsibleGroup>
          ) : null}
          {removed.length ? (
            <CollapsibleGroup title="제거된 권한" count={`${removed.length}개`} leading={mark(false)}>
              {removed.map((c) => (
                <GroupItem key={c.code} main={c.label} sub={c.area} />
              ))}
            </CollapsibleGroup>
          ) : null}
        </section>
        <hr className="border-border" />
        <section aria-labelledby="affected-title" className="flex flex-col gap-2">
          <h3 id="affected-title" className="flex items-baseline gap-1.5 text-body-strong text-foreground">
            영향받는 대상 <span className="text-caption text-muted-foreground">저장하면 바로 적용돼요</span>
          </h3>
          {impact.isError ? <Alert variant="error" title="영향받는 대상을 불러오지 못했어요." /> : null}
          {impact.data && affected === 0 ? (
            <p className="text-body text-muted-foreground">이 직위의 직원이 없어요.</p>
          ) : (
            <ImpactList impact={impact.data} pendingOnly registrationNote="승인되면 적용" />
          )}
        </section>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            취소
          </Button>
          <Button disabled={pending} onClick={onSave}>
            저장
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function changeSummary(changes: readonly PermissionChange[]): string {
  return changes.map((c) => `${c.label} ${c.on ? "켬" : "끔"}`).join(" · ");
}

function EntityLine({
  row,
  draft,
  original,
  disabled,
  onChange,
}: {
  row: EntityRow;
  draft: ReadonlySet<string>;
  original: ReadonlySet<string>;
  disabled: boolean;
  onChange: (def: PermissionDef, on: boolean) => void;
}) {
  const cells = [row.read, row.action].filter((d): d is PermissionDef => d !== null);
  const changed = cells.filter((d) => draft.has(d.code) !== original.has(d.code));
  const description = row.action?.description ?? row.read?.description ?? "";
  return (
    <li
      className={cn("flex items-center border-t border-border py-2.5 pr-3 pl-10", changed.length && "bg-info-subtle")}
    >
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-1.5">
          <span className="text-body text-foreground">{row.entity}</span>
          {changed.map((d) => (
            <span key={d.code} className="text-caption-strong text-info-text">
              {d.action} {draft.has(d.code) ? "켬" : "끔"}
            </span>
          ))}
        </span>
        <span className="text-caption text-muted-foreground">{description}</span>
      </div>
      <PermissionCell def={row.read} draft={draft} disabled={disabled} onChange={onChange} />
      {/* 관리·동작을 켜면 조회도 켜진다 (A86) */}
      <PermissionCell def={row.action} draft={draft} disabled={disabled} onChange={onChange} />
    </li>
  );
}

function PermissionCell({
  def,
  draft,
  disabled,
  onChange,
}: {
  def: PermissionDef | null;
  draft: ReadonlySet<string>;
  disabled: boolean;
  onChange: (def: PermissionDef, on: boolean) => void;
}) {
  if (!def) {
    return (
      <span aria-hidden className="w-24 text-body text-muted-foreground">
        —
      </span>
    );
  }
  return (
    <label className="flex w-24 items-center gap-1.5">
      <Checkbox
        checked={draft.has(def.code)}
        disabled={disabled}
        onCheckedChange={(v) => onChange(def, v === true)}
        aria-label={`${def.entity} ${def.action}`}
      />
      {def.action !== "조회" && def.action !== "관리" ? (
        <span className="text-caption text-muted-foreground">{def.action}</span>
      ) : null}
    </label>
  );
}
