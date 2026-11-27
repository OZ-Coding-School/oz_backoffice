import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import { managerCandidatesQuery, type ManagerCandidate } from "../api";

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
