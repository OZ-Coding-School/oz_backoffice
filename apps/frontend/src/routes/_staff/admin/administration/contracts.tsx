import { createFileRoute } from "@tanstack/react-router";

import type { ContractStatus, EducatorType } from "@/features/admin-contracts/api";
import { ContractsPage, type ContractsSearch } from "@/features/admin-contracts/components/contracts-page";

const STATUSES: ContractStatus[] = ["DRAFT", "ACTIVE", "ENDED", "TERMINATED"];
const TYPES: EducatorType[] = ["MENTOR", "INSTRUCTOR"];
const text = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** 행정 업무 > 계약 (F83). 상태 `status`, 유형 `type`, 검색 `q`, 패널 `contract`(id 또는 new) */
export const Route = createFileRoute("/_staff/admin/administration/contracts")({
  validateSearch: (search: Record<string, unknown>): ContractsSearch => {
    const out: ContractsSearch = {};
    if (STATUSES.includes(search.status as ContractStatus)) out.status = search.status as ContractStatus;
    if (TYPES.includes(search.type as EducatorType)) out.type = search.type as EducatorType;
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
