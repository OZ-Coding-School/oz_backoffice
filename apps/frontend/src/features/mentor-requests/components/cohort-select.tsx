import { useQuery } from "@tanstack/react-query";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { cohortOptions, myAssignmentsQuery } from "../api";

const ALL_COHORTS = "all";

/** 멘토 화면 기수 필터: 내 배정 기수 전체(비활성 포함), 맨 위는 전체 기수 (F43·F47) */
export function CohortSelect({
  value,
  onChange,
}: {
  value: string | undefined;
  onChange: (cohortId: string | undefined) => void;
}) {
  const assignments = useQuery(myAssignmentsQuery);
  const options = cohortOptions(assignments.data ?? []);
  return (
    <Select value={value ?? ALL_COHORTS} onValueChange={(v) => onChange(v === ALL_COHORTS ? undefined : v)}>
      <SelectTrigger aria-label="기수" className="lg:w-45">
        <SelectValue placeholder="전체 기수" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_COHORTS}>전체 기수</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.id} value={o.id}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
