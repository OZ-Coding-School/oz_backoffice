import { createFileRoute } from "@tanstack/react-router";

import type { ContractType, StatusGroup } from "@/features/admin-contracts/api";
import { ContractsPage, type ContractsSearch } from "@/features/admin-contracts/components/contracts-page";
import { TYPES } from "@/features/admin-contracts/labels";

const GROUPS: StatusGroup[] = ["open", "closed", "all"];
const text = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/**
 * 행정 업무 > 계약 (F83·F96). 과정 `bootcamp` 또는 기수 `cohort`(상단 선택기), 상태 묶음 `status`,
 * 종류 `type`, 검색 `q`, 패널 `contract`(id 또는 new)
 */
export const Route = createFileRoute("/_staff/admin/administration/contracts")({
  validateSearch: (search: Record<string, unknown>): ContractsSearch => {
    const out: ContractsSearch = {};
    const cohort = text(search.cohort);
    const bootcamp = text(search.bootcamp);
    if (cohort) out.cohort = cohort;
    else if (bootcamp) out.bootcamp = bootcamp;
    if (GROUPS.includes(search.status as StatusGroup) && search.status !== "open")
      out.status = search.status as StatusGroup;
    if (TYPES.includes(search.type as ContractType)) out.type = search.type as ContractType;
    const q = text(search.q);
    if (q) out.q = q;
    const contract = text(search.contract);
    if (contract) out.contract = contract;
    return out;
  },
  component: function Contracts() {
    return <ContractsPage search={Route.useSearch()} />;
  },
});
