import { useQuery } from "@tanstack/react-query";
import { Link, useBlocker, useNavigate } from "@tanstack/react-router";
import { BadgeCheck, GripVertical, KeyRound } from "lucide-react";
import { useMemo, useState, type DragEvent, type KeyboardEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { positionsQuery, type Position } from "@/features/admin-permissions/api";
import { assignmentScopeLabel, dataScopeLabel } from "@/features/admin-permissions/groups";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { errorText, iGa } from "@/features/admin-org/text";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { useReorderPositions } from "../api";
import { byPriority, move, orderChanged, priorityChanges } from "../order";
import { PositionSheet } from "./position-sheet";

const COLUMNS =
  "grid grid-cols-[28px_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.1fr)_minmax(0,0.8fr)_64px] items-center gap-3";

/** 조직 설정 > 직위 (F70): 우선순위순 표 + 끌어서 순서 바꾸기 + 슬라이드 패널 */
export function PositionsPage({ positionId }: { positionId?: string }) {
  const positions = useQuery(positionsQuery);
  const access = useQuery(staffAccessQuery);
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);

  if (positions.isPending || access.isPending)
    return (
      <Frame>
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      </Frame>
    );
  if (positions.isError || access.isError)
    return (
      <Frame>
        <ErrorState onRetry={() => void Promise.all([positions.refetch(), access.refetch()])} />
      </Frame>
    );

  const canManage = hasPermission(access.data, "org.position.manage");
  const sorted = [...positions.data].sort(byPriority);
  const selected = sorted.find((p) => p.id === positionId);
  const close = () => {
    setCreating(false);
    void navigate({ to: "/admin/org/positions", search: {} });
  };

  return (
    <Frame>
      {/* 서버 순서가 바뀌면(저장 후) 편집 중 순서를 새로 시작한다 */}
      <PositionTable
        key={sorted.map((p) => `${p.id}:${p.priority}`).join()}
        positions={sorted}
        selectedId={positionId}
        canManage={canManage}
        onAdd={() => setCreating(true)}
      />
      {creating || selected ? (
        <PositionSheet
          key={selected?.id ?? "new"}
          position={creating ? null : (selected ?? null)}
          positions={sorted}
          access={access.data}
          onClose={close}
        />
      ) : null}
    </Frame>
  );
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={BadgeCheck}
        title="직위"
        description="직위의 담당 방식과 데이터 범위를 정하고, 끌어서 순서를 바꿔요. 권한은 권한 메뉴에서 정해요."
      />
      {children}
    </div>
  );
}

function PositionTable({
  positions,
  selectedId,
  canManage,
  onAdd,
}: {
  positions: Position[];
  selectedId: string | undefined;
  canManage: boolean;
  onAdd: () => void;
}) {
  const [order, setOrder] = useState(positions);
  const [dragging, setDragging] = useState<number | null>(null);
  const reorder = useReorderPositions();
  const changed = orderChanged(positions, order);
  const movedIds = useMemo(
    () => new Set(order.filter((p, i) => positions[i]?.id !== p.id).map((p) => p.id)),
    [order, positions],
  );
  const blocker = useBlocker({
    shouldBlockFn: ({ next }) => changed && !reorder.isPending && next.pathname !== "/admin/org/positions",
    enableBeforeUnload: () => changed,
    withResolver: true,
  });
  const employees = positions.reduce((n, p) => n + p.employee_count, 0);

  const onDragOver = (e: DragEvent, index: number) => {
    if (dragging === null) return;
    e.preventDefault();
    if (index !== dragging) {
      setOrder((o) => move(o, dragging, index));
      setDragging(index);
    }
  };
  const onKey = (e: KeyboardEvent, index: number) => {
    const to = e.key === "ArrowUp" ? index - 1 : e.key === "ArrowDown" ? index + 1 : null;
    if (to === null || to < 0 || to >= order.length) return;
    e.preventDefault();
    setOrder((o) => move(o, index, to));
    // 움직인 손잡이에 포커스를 둔다
    requestAnimationFrame(() =>
      document.querySelector<HTMLButtonElement>(`[data-grip="${order[index]?.id}"]`)?.focus(),
    );
  };
  const onSave = async () => {
    try {
      await reorder.mutateAsync(priorityChanges(order));
      toast.success("직위 순서를 저장했어요");
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const firstMoved = order.findIndex((p) => movedIds.has(p.id));

  return (
    <section
      aria-label="직위 목록"
      className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
    >
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <span className="text-label text-muted-foreground">
          직위 {positions.length}개 · 직원 {employees}명
        </span>
        {canManage ? (
          <Button size="sm" className="ml-auto" onClick={onAdd}>
            직위 추가
          </Button>
        ) : null}
      </div>
      {order.length === 0 ? (
        <EmptyState icon={KeyRound} title="직위가 없어요" className="m-4" />
      ) : (
        <div role="table" aria-label="직위">
          <div
            role="row"
            className={cn(COLUMNS, "border-b border-border bg-muted py-2 pr-4 pl-3 text-caption text-muted-foreground")}
          >
            <span role="columnheader">
              <span className="sr-only">순서</span>
            </span>
            <span role="columnheader">이름</span>
            <span role="columnheader">담당 방식</span>
            <span role="columnheader">데이터 범위</span>
            <span role="columnheader">권한</span>
            <span role="columnheader" className="text-right">
              직원
            </span>
          </div>
          {order.map((p, i) => (
            <div
              key={p.id}
              role="row"
              aria-label={p.name}
              onDragOver={(e) => onDragOver(e, i)}
              onDrop={(e) => e.preventDefault()}
              className={cn(
                COLUMNS,
                "relative border-b border-border py-2.5 pr-4 pl-3 last:border-b-0 hover:bg-accent/60",
                selectedId === p.id && "bg-accent",
                dragging === i && "z-10 rounded-lg border border-primary bg-card shadow-md",
              )}
            >
              <span role="cell">
                {canManage ? (
                  <button
                    type="button"
                    draggable
                    data-grip={p.id}
                    aria-label={`${p.name} 순서 옮기기 (위·아래 화살표)`}
                    onDragStart={(e) => {
                      e.dataTransfer.effectAllowed = "move";
                      setDragging(i);
                    }}
                    onDragEnd={() => setDragging(null)}
                    onKeyDown={(e) => onKey(e, i)}
                    className="relative z-10 inline-flex size-6 cursor-grab items-center justify-center rounded-md text-muted-foreground hover:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none active:cursor-grabbing"
                  >
                    <GripVertical aria-hidden className="size-4" />
                  </button>
                ) : null}
              </span>
              <span role="cell" className="flex min-w-0 items-center gap-1.5">
                <Link
                  to="/admin/org/positions"
                  search={{ position: p.id }}
                  className={cn(
                    "truncate text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring",
                    selectedId === p.id && "text-primary",
                  )}
                >
                  {p.name}
                </Link>
                {movedIds.has(p.id) ? <Badge variant="info">순서 바뀜</Badge> : null}
              </span>
              <span role="cell">
                {p.assignment_scope ? (
                  <Badge variant="outline">{assignmentScopeLabel(p.assignment_scope)}</Badge>
                ) : (
                  <span className="text-body text-muted-foreground">담당 없음</span>
                )}
              </span>
              <span role="cell" className="truncate text-body text-foreground">
                {dataScopeLabel(p.data_scope)}
              </span>
              <span role="cell" className="text-body text-foreground">
                {p.permissions.length}개
              </span>
              <span role="cell" className="text-right text-body-strong text-foreground">
                {p.employee_count}명
              </span>
            </div>
          ))}
        </div>
      )}
      {changed ? (
        <div className="sticky bottom-0 flex items-center gap-3 border-t border-border bg-card px-6 py-3">
          <span aria-hidden className="size-2 rounded-full bg-warning" />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="text-body-strong text-foreground">순서가 바뀌었어요</span>
            <span className="truncate text-caption text-muted-foreground">
              {iGa(order[firstMoved]?.name ?? "")} {firstMoved + 1}번째로 · 저장하면 목록과 선택지 순서가 바뀌어요
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={() => setOrder(positions)}>
            되돌리기
          </Button>
          <Button size="sm" disabled={reorder.isPending} onClick={() => void onSave()}>
            순서 저장
          </Button>
        </div>
      ) : null}
      <DiscardDialog blocker={blocker} />
    </section>
  );
}
