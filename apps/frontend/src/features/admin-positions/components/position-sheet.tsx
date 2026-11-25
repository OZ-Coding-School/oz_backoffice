import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { CollapsibleGroup, GroupItem } from "@/components/collapsible-group";
import { PanelActions, PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { permissionDefsQuery, type PermissionDef, type Position } from "@/features/admin-permissions/api";
import { assignmentScopeLabel, dataScopeLabel } from "@/features/admin-permissions/groups";
import { hasImpact, impactQuery } from "@/features/admin-org/api";
import { ImpactList } from "@/features/admin-org/components/impact-list";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { errorText, eul } from "@/features/admin-org/text";
import { hasPermission, type StaffAccess } from "@/features/staff/api";

import { useDeletePosition, useSavePosition } from "../api";
import { nextPriority } from "../order";

const NONE = "none";
const SCOPE_HELP =
  "과정 담당은 팀의 과정 여러 개, 기수 담당은 팀 과정의 기수 하나를 맡아요. 담당 없음이면 맡지 않아요.";
const DATA_HELP =
  "'담당 과정·기수만'이면 맡은 과정·기수의 데이터만, '모든 과정·기수'면 전체를 볼 수 있어요. 기수와 상관없는 데이터는 늘 전체예요.";

const schema = z.object({
  name: z.string().trim().min(1, "직위 이름을 적어 주세요.").max(20, "직위 이름은 20자까지예요."),
  assignment_scope: z.enum(["COURSE", "COHORT", NONE]),
  data_scope: z.enum(["ASSIGNED", "ALL"]),
});
type Values = z.infer<typeof schema>;

/** 직위 패널 (F68·F70). position이 null이면 추가 */
export function PositionSheet({
  position,
  positions,
  access,
  onClose,
}: {
  position: Position | null;
  positions: Position[];
  access: StaffAccess;
  onClose: () => void;
}) {
  const canManage = hasPermission(access, "org.position.manage");
  const [editing, setEditing] = useState(position === null);
  const [deleting, setDeleting] = useState(false);
  const rank = position ? positions.findIndex((p) => p.id === position.id) + 1 : 0;
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={position?.name ?? "새 직위"}
          description={position ? `직위 · ${rank}번째` : "직위"}
          badges={editing && position ? <Badge variant="info">수정 중</Badge> : null}
          actions={
            canManage && !editing && position ? (
              <PanelActions onEdit={() => setEditing(true)} onDelete={() => setDeleting(true)} />
            ) : null
          }
          onClose={onClose}
        />
        {editing ? (
          <PositionForm
            position={position}
            positions={positions}
            onDone={() => (position ? setEditing(false) : onClose())}
          />
        ) : position ? (
          <PositionView position={position} access={access} />
        ) : null}
        {deleting && position ? (
          <DeletePositionDialog position={position} onClose={() => setDeleting(false)} onDeleted={onClose} />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function PositionView({ position, access }: { position: Position; access: StaffAccess }) {
  // 직원 목록은 영향 조회로, 권한 정의는 권한 조회 권한이 있을 때만 읽는다
  const canSeeEmployees =
    access.is_super_admin ||
    hasPermission(access, "org.position.manage") ||
    hasPermission(access, "access.role.manage");
  const canSeePermissions = access.is_super_admin || hasPermission(access, "access.role.read");
  const impact = useQuery({ ...impactQuery("position", position.id), enabled: canSeeEmployees });
  const defs = useQuery({ ...permissionDefsQuery, enabled: canSeePermissions });
  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
      <PanelSection title="기본 정보">
        <PanelRow label="이름">{position.name}</PanelRow>
        <PanelRow label="담당 방식" help={SCOPE_HELP}>
          {assignmentScopeLabel(position.assignment_scope)}
        </PanelRow>
        <PanelRow label="데이터 범위" help={DATA_HELP}>
          {dataScopeLabel(position.data_scope)}
        </PanelRow>
        <PanelRow label="직원">{position.employee_count}명</PanelRow>
      </PanelSection>
      {canSeeEmployees ? (
        <PanelSection title="직원">
          {impact.data ? (
            impact.data.employees.length ? (
              <PanelList
                label="직원"
                items={impact.data.employees.map((e) => ({
                  id: e.id,
                  name: e.name,
                  meta: e.team_name ?? e.department_name,
                }))}
              />
            ) : (
              <p className="text-body text-muted-foreground">이 직위의 직원이 없어요.</p>
            )
          ) : impact.isError ? (
            <Alert variant="error" title="직원을 불러오지 못했어요." />
          ) : (
            <p className="text-body text-muted-foreground">불러오는 중…</p>
          )}
        </PanelSection>
      ) : null}
      <PanelSection title={`권한 ${position.permissions.length}개`}>
        {!canSeePermissions ? (
          <p className="text-body text-muted-foreground">권한 내용은 권한 메뉴에서 볼 수 있어요.</p>
        ) : defs.data ? (
          <PermissionGroups codes={position.permissions} defs={defs.data} />
        ) : (
          <p className="text-body text-muted-foreground">불러오는 중…</p>
        )}
      </PanelSection>
    </div>
  );
}

/** 켜진 권한을 영역별 접는 상자로 (읽기만, 처음엔 접힘) */
function PermissionGroups({ codes, defs }: { codes: string[]; defs: PermissionDef[] }) {
  const groups = useMemo(() => {
    const on = new Set(codes);
    const byArea = new Map<string, PermissionDef[]>();
    for (const d of defs) if (on.has(d.code)) byArea.set(d.area, [...(byArea.get(d.area) ?? []), d]);
    return [...byArea.entries()];
  }, [codes, defs]);
  if (!groups.length) return <p className="text-body text-muted-foreground">켜진 권한이 없어요.</p>;
  return (
    <div className="flex flex-col gap-2">
      {groups.map(([area, items]) => (
        <CollapsibleGroup key={area} title={area} count={`${items.length}개`}>
          {items.map((d) => (
            <GroupItem key={d.code} main={`${d.entity} · ${d.action}`} />
          ))}
        </CollapsibleGroup>
      ))}
    </div>
  );
}

function PositionForm({
  position,
  positions,
  onDone,
}: {
  position: Position | null;
  positions: Position[];
  onDone: () => void;
}) {
  const id = useId();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: position?.name ?? "",
      assignment_scope: position?.assignment_scope ?? NONE,
      data_scope: position?.data_scope ?? "ASSIGNED",
    },
  });
  const save = useSavePosition(position?.id ?? null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<Values | null>(null);
  const dirty = form.formState.isDirty;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const { errors } = form.formState;

  const persist = async (v: Values) => {
    setError(null);
    try {
      await save.mutateAsync({
        name: v.name,
        priority: position?.priority ?? nextPriority(positions),
        assignment_scope: v.assignment_scope === NONE ? null : v.assignment_scope,
        data_scope: v.data_scope,
      });
      form.reset(v);
      setConfirming(null);
      toast.success(position ? `${v.name} 직위를 저장했어요` : `${v.name} 직위를 만들었어요`);
      onDone();
    } catch (e) {
      setConfirming(null);
      if (e instanceof ApiError && e.code === "position_name_taken")
        form.setError("name", { message: "같은 이름의 직위가 있어요." });
      else setError(errorText(e));
    }
  };

  // 담당 방식·데이터 범위를 바꾸면 바뀐 항목과 영향받는 대상을 먼저 보여 준다 (A93·F70)
  const onSubmit = form.handleSubmit((v) => {
    const scopeChanged =
      position && (v.assignment_scope !== (position.assignment_scope ?? NONE) || v.data_scope !== position.data_scope);
    return scopeChanged ? setConfirming(v) : persist(v);
  });

  return (
    <form
      aria-label={position ? "직위 수정" : "직위 추가"}
      noValidate
      onSubmit={(e) => void onSubmit(e)}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <PanelSection title="기본 정보">
          <PanelRow label="이름" htmlFor={`${id}-name`}>
            <Input id={`${id}-name`} maxLength={20} aria-invalid={!!errors.name} {...form.register("name")} />
            {errors.name ? (
              <p className="mt-1 text-caption font-normal text-destructive-text">{errors.name.message}</p>
            ) : null}
          </PanelRow>
          <PanelRow label="담당 방식" htmlFor={`${id}-scope`} help={SCOPE_HELP}>
            <Controller
              control={form.control}
              name="assignment_scope"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id={`${id}-scope`} className="font-normal">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="COURSE">과정 담당</SelectItem>
                    <SelectItem value="COHORT">기수 담당</SelectItem>
                    <SelectItem value={NONE}>담당 없음</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </PanelRow>
          <PanelRow label="데이터 범위" htmlFor={`${id}-data`} help={DATA_HELP}>
            <Controller
              control={form.control}
              name="data_scope"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id={`${id}-data`} className="font-normal">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ASSIGNED">담당 과정·기수만</SelectItem>
                    <SelectItem value="ALL">모든 과정·기수</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </PanelRow>
          {position ? <PanelRow label="직원">{position.employee_count}명</PanelRow> : null}
        </PanelSection>
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
        <Button type="button" variant="outline" onClick={onDone}>
          취소
        </Button>
        <Button type="submit" disabled={save.isPending}>
          저장
        </Button>
      </div>
      {confirming && position ? (
        <ChangeDialog
          position={position}
          values={confirming}
          pending={save.isPending}
          onCancel={() => setConfirming(null)}
          onConfirm={() => void persist(confirming)}
        />
      ) : null}
      <DiscardDialog blocker={blocker} />
    </form>
  );
}

/** 담당 방식·데이터 범위 변경 확인: 위 '바뀐 항목', 아래 '영향받는 대상' (A93·F70) */
function ChangeDialog({
  position,
  values,
  pending,
  onCancel,
  onConfirm,
}: {
  position: Position;
  values: Values;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const impact = useQuery(impactQuery("position", position.id));
  const nextScope = values.assignment_scope === NONE ? null : values.assignment_scope;
  const rows = [
    nextScope !== position.assignment_scope
      ? ["담당 방식", assignmentScopeLabel(position.assignment_scope), assignmentScopeLabel(nextScope)]
      : null,
    values.data_scope !== position.data_scope
      ? ["데이터 범위", dataScopeLabel(position.data_scope), dataScopeLabel(values.data_scope)]
      : null,
  ].filter((r): r is string[] => r !== null);
  const affected = impact.data
    ? impact.data.employees.length + impact.data.registrations.filter((r) => r.status === "PENDING").length
    : 0;
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onCancel())}>
      <DialogContent className="flex max-w-150 flex-col gap-5 p-6">
        <div className="flex flex-col gap-1 pr-8">
          <DialogTitle className="text-h2 text-foreground">{position.name} 직위를 바꿀까요?</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            바뀐 항목을 확인하고 저장하세요.
            {nextScope !== position.assignment_scope
              ? " 담당 방식이 바뀌어도 직원의 지금 담당은 그대로라 직원 화면에서 다시 골라야 해요."
              : ""}
          </DialogDescription>
        </div>
        <section aria-label="바뀐 항목" className="flex flex-col gap-2">
          <h3 className="text-body-strong text-foreground">바뀐 항목</h3>
          <dl className="flex flex-col gap-2 rounded-lg border border-border px-3.5 py-3">
            {rows.map(([label, before, after]) => (
              <div key={label} className="grid grid-cols-[96px_minmax(0,1fr)] items-center gap-3">
                <dt className="text-body text-muted-foreground">{label}</dt>
                <dd className="text-body-strong text-foreground">
                  {before} → {after}
                </dd>
              </div>
            ))}
          </dl>
        </section>
        <hr className="border-border" />
        <section aria-label="영향받는 대상" className="flex flex-col gap-2">
          <h3 className="flex items-baseline gap-1.5 text-body-strong text-foreground">
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
          <Button disabled={!impact.data || pending} onClick={onConfirm}>
            저장
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 직위 삭제: 직원·신청이 남아 있으면 지울 수 없어 그 대상을 보여 준다 (A93·F70) */
function DeletePositionDialog({
  position,
  onClose,
  onDeleted,
}: {
  position: Position;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const impact = useQuery(impactQuery("position", position.id));
  const remove = useDeletePosition();
  const [error, setError] = useState<string | null>(null);
  const blocked = impact.data ? hasImpact(impact.data) : false;
  const onDelete = async () => {
    setError(null);
    try {
      await remove.mutateAsync(position.id);
      toast.success(`${position.name} 직위를 삭제했어요`);
      onDeleted();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="pr-8 text-h2 text-foreground">
          {blocked ? `${eul(position.name)} 지울 수 없어요` : `${eul(position.name)} 삭제할까요?`}
        </DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {blocked
            ? "아래 직원·가입 신청을 먼저 다른 직위로 옮겨야 지울 수 있어요."
            : "직위의 권한 설정도 함께 사라져요. 되돌릴 수 없어요."}
        </DialogDescription>
        {impact.isError ? <Alert variant="error" title="영향받는 대상을 불러오지 못했어요." /> : null}
        {blocked ? <ImpactList impact={impact.data} /> : null}
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            {blocked ? "닫기" : "취소"}
          </Button>
          {blocked ? null : (
            <Button variant="destructive" disabled={!impact.data || remove.isPending} onClick={() => void onDelete()}>
              삭제
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
