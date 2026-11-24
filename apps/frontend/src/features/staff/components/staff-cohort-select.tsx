import { useQuery } from "@tanstack/react-query";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { staffAccessQuery } from "../api";
import { staffCohortLabel } from "../labels";

const ALL = "all";

/** 운영진 목록의 기수 필터: 담당 기수(A81, 진행 중 먼저), 맨 위는 전체 기수 */
export function StaffCohortSelect({
  value,
  onChange,
}: {
  value: string | undefined;
  onChange: (cohortId: string | undefined) => void;
}) {
  const access = useQuery(staffAccessQuery);
  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? undefined : v)}>
      <SelectTrigger aria-label="기수" className="w-56">
        <SelectValue placeholder="전체 기수" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>전체 기수</SelectItem>
        {(access.data?.cohorts ?? []).map((c) => (
          <SelectItem key={c.id} value={c.id}>
            {staffCohortLabel(c)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
