import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { mentorsQuery } from "@/features/admin-mentors/api";
import { maskPhone } from "@/features/profile/mask";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import {
  managerCandidatesQuery,
  useMoveContract,
  useUpdateContract,
  type Contract,
  type ManagerCandidate,
} from "../api";
import { contractError } from "../labels";

export interface ManagerChoice {
  id: string;
  name: string;
}

const managerMeta = (m: ManagerCandidate) =>
  [m.department_name, m.team_name, m.position_name].filter(Boolean).join(" · ");

/** 담당 직원 고르기 (A103): 검색 + 후보 목록(처음엔 나를 맨 앞에) */
export function ManagerList({
  value,
  onChange,
}: {
  value: ManagerChoice | null;
  onChange: (choice: ManagerChoice) => void;
}) {
  const [q, setQ] = useState("");
  const term = useDebounced(q.trim());
  const found = useQuery(managerCandidatesQuery(term));
  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          aria-label="담당 직원 검색"
          placeholder="이름·이메일 검색"
          value={q}
          maxLength={50}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9 font-normal"
        />
      </div>
      {found.isPending ? (
        <Spinner />
      ) : (found.data ?? []).length === 0 ? (
        <p className="text-body text-muted-foreground">찾는 직원이 없어요.</p>
      ) : (
        <ul
          role="listbox"
          aria-label="담당 직원 후보"
          className="max-h-56 divide-y divide-border overflow-y-auto rounded-md border border-border"
        >
          {(found.data ?? []).map((m) => {
            const selected = m.employee_id === value?.id;
            return (
              <li
                key={m.employee_id}
                role="option"
                aria-selected={selected}
                tabIndex={0}
                onClick={() => onChange({ id: m.employee_id, name: m.name })}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onChange({ id: m.employee_id, name: m.name });
                  }
                }}
                className={cn(
                  "flex cursor-pointer items-center gap-2 px-3 py-2 outline-none hover:bg-accent focus-visible:bg-accent",
                  selected && "bg-accent",
                )}
              >
                <span className="text-body-strong text-foreground">
                  {m.name}
                  {m.is_me ? " (나)" : ""}
                </span>
                <span className="min-w-0 flex-1 truncate text-caption text-muted-foreground">{managerMeta(m)}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** 담당 직원 변경: 확정한 계약도 바꿀 수 있다 (A25) */
export function ManagerDialog({ contract: c, onClose }: { contract: Contract; onClose: () => void }) {
  const save = useUpdateContract(c.id);
  const [choice, setChoice] = useState<ManagerChoice | null>(null);
  const submit = async () => {
    if (!choice) return;
    try {
      await save.mutateAsync({ manager_employee_id: choice.id });
      toast.success(`담당 직원을 ${choice.name}(으)로 바꿨어요`);
      onClose();
    } catch (e) {
      toast.error(contractError(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">담당 직원 변경</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          지금 담당: {c.manager_name ?? "—"}
        </DialogDescription>
        <ManagerList value={choice} onChange={setChoice} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            돌아가기
          </Button>
          <Button
            disabled={!choice || choice.id === c.manager_employee_id || save.isPending}
            onClick={() => void submit()}
          >
            변경
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 다른 멘토로 옮기기 (A104): 멘토 검색 + 고르기 */
export function MoveDialog({ contract: c, onClose }: { contract: Contract; onClose: () => void }) {
  const move = useMoveContract(c.id);
  const [q, setQ] = useState("");
  const term = useDebounced(q.trim());
  const found = useInfiniteQuery(mentorsQuery({ q: term || undefined }));
  const mentors = (found.data?.pages[0]?.items ?? []).filter((m) => m.id !== c.mentor_id);
  const [choice, setChoice] = useState<{ id: string; name: string } | null>(null);
  const submit = async () => {
    if (!choice) return;
    try {
      await move.mutateAsync(choice.id);
      toast.success(`계약을 ${choice.name} 멘토로 옮겼어요`);
      onClose();
    } catch (e) {
      toast.error(contractError(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">다른 멘토로 옮기기</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          옮기면 지금 가입 전 멘토에 다른 계약이 없을 때 그 멘토는 지워져요.
        </DialogDescription>
        <div className="relative">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="멘토 검색"
            placeholder="이름·이메일·휴대폰·닉네임 검색"
            value={q}
            maxLength={50}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
        {found.isPending ? (
          <Spinner />
        ) : mentors.length === 0 ? (
          <p className="text-body text-muted-foreground">찾는 멘토가 없어요.</p>
        ) : (
          <ul
            role="listbox"
            aria-label="옮길 멘토"
            className="max-h-64 divide-y divide-border overflow-y-auto rounded-md border border-border"
          >
            {mentors.map((m) => {
              const selected = m.id === choice?.id;
              const pick = () => setChoice({ id: m.id, name: m.name });
              return (
                <li
                  key={m.id}
                  role="option"
                  aria-selected={selected}
                  tabIndex={0}
                  onClick={pick}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      pick();
                    }
                  }}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 px-3 py-2 outline-none hover:bg-accent focus-visible:bg-accent",
                    selected && "bg-accent",
                  )}
                >
                  <span className="text-body-strong text-foreground">
                    {m.name}
                    {m.display_name !== m.name ? `(${m.display_name})` : ""}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-caption text-muted-foreground">
                    {[m.email, maskPhone(m.phone_number)].filter(Boolean).join(" · ")}
                    {m.is_registered ? "" : " · 가입 전"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            돌아가기
          </Button>
          <Button disabled={!choice || move.isPending} onClick={() => void submit()}>
            옮기기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
