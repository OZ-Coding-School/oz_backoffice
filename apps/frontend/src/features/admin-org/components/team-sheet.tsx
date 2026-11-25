import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { PanelActions, PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import type { StaffOptions } from "@/features/auth/staff-api";

import { hasImpact, impactQuery, useDeleteTeam, useSaveTeam, type Department, type Team } from "../api";
import { eul, errorText } from "../text";
import { ImpactList } from "./impact-list";
import { DiscardDialog } from "./shared";

const schema = z.object({
  name: z.string().trim().min(1, "팀 이름을 적어 주세요.").max(20, "팀 이름은 20자까지예요."),
  department_id: z.string().min(1, "부서를 골라 주세요."),
  description: z.string().max(500, "설명은 500자까지예요."),
  bootcamp_ids: z.array(z.string()),
});
type Values = z.infer<typeof schema>;
type Bootcamp = StaffOptions["bootcamps"][number];

const DEPARTMENT_HELP = "부서를 바꾸면 팀의 직원·가입 신청이 함께 그 부서로 옮겨 가요.";

/** 팀 패널 (F68·F69). team이 null이면 추가 */
export function TeamSheet({
  team,
  departments,
  teams,
  bootcamps,
  canManage,
  onClose,
}: {
  team: Team | null;
  departments: Department[];
  teams: Team[];
  bootcamps: Bootcamp[];
  canManage: boolean;
  onClose: () => void;
}) {
  const [editing, setEditing] = useState(team === null);
  const [deleting, setDeleting] = useState(false);
  const department = departments.find((d) => d.id === team?.department_id);
  const bootcampName = (id: string) => bootcamps.find((b) => b.id === id)?.name ?? "—";
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={team?.name ?? "새 팀"}
          description={department ? `${department.name} · 팀` : "팀"}
          badges={editing && team ? <Badge variant="info">수정 중</Badge> : null}
          actions={
            canManage && !editing ? (
              <PanelActions onEdit={() => setEditing(true)} onDelete={() => setDeleting(true)} />
            ) : null
          }
          onClose={onClose}
        />
        {editing ? (
          <TeamForm
            team={team}
            departments={departments}
            teams={teams}
            bootcamps={bootcamps}
            onDone={() => (team ? setEditing(false) : onClose())}
          />
        ) : team ? (
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
            <PanelSection title="기본 정보">
              <PanelRow label="이름">{team.name}</PanelRow>
              <PanelRow label="부서">{department?.name ?? "—"}</PanelRow>
              <PanelRow label="설명">
                {team.description ? (
                  <span className="whitespace-pre-line">{team.description}</span>
                ) : (
                  <span className="font-normal text-muted-foreground">없음</span>
                )}
              </PanelRow>
              <PanelRow label="직원">{team.employee_count}명</PanelRow>
            </PanelSection>
            <PanelSection title="담당 과정">
              {team.bootcamp_ids.length ? (
                <PanelList label="담당 과정" items={team.bootcamp_ids.map((id) => ({ id, name: bootcampName(id) }))} />
              ) : (
                <p className="text-body text-muted-foreground">담당 과정이 없어요.</p>
              )}
            </PanelSection>
          </div>
        ) : null}
        {deleting && team ? (
          <DeleteTeamDialog
            team={team}
            teams={teams}
            departments={departments}
            onClose={() => setDeleting(false)}
            onDeleted={onClose}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function TeamForm({
  team,
  departments,
  teams,
  bootcamps,
  onDone,
}: {
  team: Team | null;
  departments: Department[];
  teams: Team[];
  bootcamps: Bootcamp[];
  onDone: () => void;
}) {
  const id = useId();
  const initialBootcamps = team?.bootcamp_ids ?? [];
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: team?.name ?? "",
      department_id: team?.department_id ?? (departments.length === 1 ? (departments[0]?.id ?? "") : ""),
      description: team?.description ?? "",
      bootcamp_ids: initialBootcamps,
    },
  });
  const save = useSaveTeam(team?.id ?? null);
  const [error, setError] = useState<string | null>(null);
  const [moving, setMoving] = useState<Values | null>(null);
  const dirty = form.formState.isDirty;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const { errors } = form.formState;
  const chosen = useWatch({ control: form.control, name: "bootcamp_ids" });
  const ownerOf = (bootcampId: string) => {
    const owner = bootcamps.find((b) => b.id === bootcampId)?.team_id;
    return owner && owner !== team?.id ? teams.find((t) => t.id === owner)?.name : undefined;
  };

  const persist = async (v: Values) => {
    setError(null);
    try {
      await save.mutateAsync({
        body: { name: v.name, department_id: v.department_id, description: v.description.trim() || null },
        bootcampIds: v.bootcamp_ids,
        before: initialBootcamps,
      });
      form.reset(v);
      setMoving(null);
      toast.success(team ? `${v.name} 팀을 저장했어요` : `${v.name} 팀을 만들었어요`);
      onDone();
    } catch (e) {
      setMoving(null);
      if (e instanceof ApiError && e.code === "team_name_taken")
        form.setError("name", { message: "같은 부서에 같은 이름의 팀이 있어요." });
      else setError(errorText(e));
    }
  };

  // 부서를 바꾸면 함께 옮겨 갈 직원·신청을 먼저 보여 준다 (A93)
  const onSubmit = form.handleSubmit((v) =>
    team && v.department_id !== team.department_id ? setMoving(v) : persist(v),
  );

  return (
    <form
      aria-label={team ? "팀 수정" : "팀 추가"}
      noValidate
      onSubmit={(e) => void onSubmit(e)}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <PanelSection title="기본 정보">
          <PanelRow label="이름" htmlFor={`${id}-name`}>
            <Input id={`${id}-name`} maxLength={20} aria-invalid={!!errors.name} {...form.register("name")} />
            {errors.name ? <FieldError>{errors.name.message}</FieldError> : null}
          </PanelRow>
          <PanelRow label="부서" htmlFor={`${id}-department`} {...(team ? { help: DEPARTMENT_HELP } : {})}>
            <Controller
              control={form.control}
              name="department_id"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id={`${id}-department`} aria-invalid={!!errors.department_id} className="font-normal">
                    <SelectValue placeholder="부서를 선택하세요" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {d.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.department_id ? <FieldError>{errors.department_id.message}</FieldError> : null}
          </PanelRow>
          <PanelRow label="설명" htmlFor={`${id}-description`} top>
            <Textarea id={`${id}-description`} rows={3} maxLength={500} {...form.register("description")} />
          </PanelRow>
          {team ? <PanelRow label="직원">{team.employee_count}명</PanelRow> : null}
        </PanelSection>
        <PanelSection title="담당 과정">
          {chosen.length ? (
            <PanelList
              label="담당 과정"
              items={chosen.map((b) => ({ id: b, name: bootcamps.find((x) => x.id === b)?.name ?? "—" }))}
              onRemove={(b) =>
                form.setValue(
                  "bootcamp_ids",
                  chosen.filter((x) => x !== b),
                  { shouldDirty: true },
                )
              }
            />
          ) : (
            <p className="text-body text-muted-foreground">담당 과정이 없어요.</p>
          )}
          <Select
            value=""
            onValueChange={(b) => form.setValue("bootcamp_ids", [...chosen, b], { shouldDirty: true })}
            disabled={chosen.length === bootcamps.length}
          >
            <SelectTrigger aria-label="담당 과정 추가" className="font-normal">
              <SelectValue placeholder="담당 과정 추가" />
            </SelectTrigger>
            <SelectContent>
              {[...bootcamps]
                .filter((b) => !chosen.includes(b.id))
                .sort((a, b) => a.name.localeCompare(b.name, "ko"))
                .map((b) => {
                  const owner = ownerOf(b.id);
                  return (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                      {owner ? ` (지금 ${owner} → 이 팀으로 옮겨 와요)` : ""}
                    </SelectItem>
                  );
                })}
            </SelectContent>
          </Select>
        </PanelSection>
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex items-center gap-2 border-t border-border px-6 py-3">
        <div className="ml-auto flex gap-2">
          <Button type="button" variant="outline" onClick={onDone}>
            취소
          </Button>
          <Button type="submit" disabled={save.isPending}>
            저장
          </Button>
        </div>
      </div>
      {moving && team ? (
        <MoveTeamDialog
          team={team}
          department={departments.find((d) => d.id === moving.department_id)}
          pending={save.isPending}
          onCancel={() => setMoving(null)}
          onConfirm={() => void persist(moving)}
        />
      ) : null}
      <DiscardDialog blocker={blocker} />
    </form>
  );
}

function FieldError({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-caption font-normal text-destructive-text">{children}</p>;
}

/** 팀의 부서 이동: 함께 옮겨 갈 직원·신청 (A93) */
function MoveTeamDialog({
  team,
  department,
  pending,
  onCancel,
  onConfirm,
}: {
  team: Team;
  department: Department | undefined;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const impact = useQuery(impactQuery("team", team.id));
  const moved = impact.data && (impact.data.employees.length || impact.data.registrations.length);
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onCancel())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="pr-8 text-h2 text-foreground">
          {eul(team.name)} {department?.name ?? "다른 부서"}로 옮길까요?
        </DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {moved ? "아래 직원·가입 신청이 함께 그 부서로 옮겨 가요." : "함께 옮겨 갈 직원·가입 신청이 없어요."}
        </DialogDescription>
        {impact.isError ? <Alert variant="error" title="영향받는 대상을 불러오지 못했어요." /> : null}
        {impact.data && moved ? (
          <ImpactList impact={{ ...impact.data, bootcamps: [], teams: [] }} />
        ) : impact.isPending ? (
          <ImpactList impact={undefined} />
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            취소
          </Button>
          <Button disabled={!impact.data || pending} onClick={onConfirm}>
            옮기고 저장
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 팀 삭제: 직원·신청·담당 과정이 있으면 옮길 팀을 골라야 지운다 (A93·F69) */
function DeleteTeamDialog({
  team,
  teams,
  departments,
  onClose,
  onDeleted,
}: {
  team: Team;
  teams: Team[];
  departments: Department[];
  onClose: () => void;
  onDeleted: () => void;
}) {
  const id = useId();
  const impact = useQuery(impactQuery("team", team.id));
  const remove = useDeleteTeam();
  const [moveTo, setMoveTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const needsMove = impact.data ? hasImpact(impact.data) : false;
  const others = teams.filter((t) => t.id !== team.id);
  const onDelete = async () => {
    setError(null);
    try {
      await remove.mutateAsync({ id: team.id, moveTo: needsMove ? moveTo : null });
      toast.success(`${team.name} 팀을 삭제했어요`);
      onDeleted();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="pr-8 text-h2 text-foreground">{eul(team.name)} 삭제할까요?</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {needsMove
            ? "아래 대상이 '옮길 팀'으로 함께 옮겨진 뒤 팀이 삭제돼요. 되돌릴 수 없어요."
            : "되돌릴 수 없어요."}
        </DialogDescription>
        {impact.isError ? <Alert variant="error" title="영향받는 대상을 불러오지 못했어요." /> : null}
        {impact.isPending || needsMove ? <ImpactList impact={impact.data} /> : null}
        {needsMove ? (
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${id}-move`} className="text-label text-foreground">
              옮길 팀
            </label>
            <Select value={moveTo} onValueChange={setMoveTo} disabled={!others.length}>
              <SelectTrigger id={`${id}-move`}>
                <SelectValue placeholder={others.length ? "옮길 팀을 선택하세요" : "옮길 수 있는 팀이 없어요"} />
              </SelectTrigger>
              <SelectContent>
                {others.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {departments.find((d) => d.id === t.department_id)?.name ?? "—"} · {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button
            variant="destructive"
            disabled={!impact.data || (needsMove && !moveTo) || remove.isPending}
            onClick={() => void onDelete()}
          >
            삭제
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
