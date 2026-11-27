import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { postPhoto } from "@/features/mentor-profile/api";

export type Contract = components["schemas"]["ContractResponse"];
export type ContractStatus = components["schemas"]["ContractStatus"];
export type ContractType = components["schemas"]["ContractType"];
export type SettlementType = components["schemas"]["SettlementType"];
export type PriceUnit = components["schemas"]["PriceUnit"];
export type VatType = components["schemas"]["VatType"];
export type TimeBasis = components["schemas"]["MentoringTimeBasis"];
export type TerminationReason = components["schemas"]["TerminationReason"];
export type ContractFile = components["schemas"]["ContractFileResponse"];
export type ManagerCandidate = components["schemas"]["ManagerCandidateResponse"];
export type ContractFields = components["schemas"]["ContractFields"];
export type ContractUpdate = components["schemas"]["ContractUpdate"];
export type AmendmentChanges = components["schemas"]["AmendmentChanges"];
export type Amendment = components["schemas"]["AmendmentResponse"];
export type ContractTypeCounts = components["schemas"]["ContractTypeCounts"];

export const PAGE_SIZE = 20;

/** 상태 묶음 (F96): 진행 중인 계약 · 끝난 계약 · 전체 */
export type StatusGroup = "open" | "closed" | "all";
export const STATUS_GROUPS: Record<StatusGroup, ContractStatus[]> = {
  open: ["DRAFT", "IN_PROGRESS", "SIGNED", "ACTIVE"],
  closed: ["ENDED", "TERMINATED", "CANCELED"],
  all: [],
};

export interface ContractFilter {
  /** 과정 전체 (과정 공통 + 그 과정의 기수 계약) */
  bootcampId?: string;
  /** 기수 (그 기수 계약 + 같은 과정의 과정 공통 계약, A112) */
  cohortId?: string;
  group?: StatusGroup;
  type?: ContractType;
  q?: string;
}

export const contractKeys = {
  all: ["admin-contracts"] as const,
  list: (f: ContractFilter) =>
    [
      "admin-contracts",
      "list",
      f.bootcampId ?? "",
      f.cohortId ?? "",
      f.group ?? "open",
      f.type ?? "",
      f.q ?? "",
    ] as const,
  detail: (id: string) => ["admin-contracts", "detail", id] as const,
  amendments: (id: string) => ["admin-contracts", "amendments", id] as const,
  managers: (q: string) => ["admin-contracts", "managers", q] as const,
};

/** 계약 목록 (A109·A112). 20개씩 이어 붙인다. 최근 등록부터, `counts`는 종류별 건수 */
export function contractsQuery(f: ContractFilter) {
  const statuses = STATUS_GROUPS[f.group ?? "open"];
  return infiniteQueryOptions({
    queryKey: contractKeys.list(f),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/contracts", {
          params: {
            query: {
              limit: PAGE_SIZE,
              offset: pageParam,
              ...(f.cohortId
                ? { cohort_id: f.cohortId, include_bootcamp_common: true }
                : f.bootcampId
                  ? { bootcamp_id: f.bootcampId }
                  : {}),
              ...(statuses.length ? { status: statuses } : {}),
              ...(f.type ? { contract_type: [f.type] } : {}),
              ...(f.q ? { q: f.q } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

export function contractQuery(id: string) {
  return queryOptions({
    queryKey: contractKeys.detail(id),
    queryFn: () => unwrap(api.GET("/api/v1/admin/contracts/{contract_id}", { params: { path: { contract_id: id } } })),
  });
}

/** 변경 이력 (A109⑨) */
export function amendmentsQuery(id: string) {
  return queryOptions({
    queryKey: contractKeys.amendments(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/contracts/{contract_id}/amendments", { params: { path: { contract_id: id } } })),
  });
}

/** 담당 직원 후보 (A103): 검색어가 없으면 나를 맨 앞에 */
export function managerCandidatesQuery(q: string) {
  return queryOptions({
    queryKey: contractKeys.managers(q),
    queryFn: () => unwrap(api.GET("/api/v1/admin/contracts/manager-candidates", { params: { query: q ? { q } : {} } })),
    staleTime: 60_000,
  });
}

/** 계약서 다운로드 주소 (만료 10분) */
export async function contractFileUrl(id: string): Promise<string> {
  const res = await unwrap(
    api.GET("/api/v1/admin/contracts/{contract_id}/file-url", { params: { path: { contract_id: id } } }),
  );
  return res.url;
}

/** 변경 계약서 다운로드 주소 */
export async function amendmentFileUrl(contractId: string, amendmentId: string): Promise<string> {
  const res = await unwrap(
    api.GET("/api/v1/admin/contracts/{contract_id}/amendments/{amendment_id}/file-url", {
      params: { path: { contract_id: contractId, amendment_id: amendmentId } },
    }),
  );
  return res.url;
}

/** 계약서 올리기 (A26): 요청 → S3로 바로 → 확정. 확정된 파일을 돌려준다 */
export async function uploadContractFile(file: File): Promise<ContractFile> {
  const ticket = await unwrap(api.POST("/api/v1/admin/contract-files/uploads", { body: { file_name: file.name } }));
  await postPhoto(ticket, file, file.name);
  return unwrap(
    api.POST("/api/v1/admin/contract-files/uploads/{upload_id}/confirm", {
      params: { path: { upload_id: ticket.upload_id } },
    }),
  );
}

/** 계약이 바뀌면 그 계약·목록·이력·멘토(계약 수·가입 전 멘토·배정)를 다시 읽는다 */
function useRefresh() {
  const client = useQueryClient();
  return (contract?: Contract) => {
    if (contract) {
      client.setQueryData(contractKeys.detail(contract.id), contract);
      void client.invalidateQueries({ queryKey: contractKeys.amendments(contract.id) });
    }
    void client.invalidateQueries({ queryKey: ["admin-contracts", "list"] });
    void client.invalidateQueries({ queryKey: ["admin-mentors"] });
  };
}

/** 계약 추가. `start`면 저장한 뒤 바로 진행 시작(`/progress`) */
export function useCreateContract() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ body, start }: { body: ContractFields; start: boolean }) => {
      const saved = await unwrap(api.POST("/api/v1/admin/contracts", { body }));
      if (!start) return { saved, started: false as const };
      try {
        const progressed = await unwrap(
          api.POST("/api/v1/admin/contracts/{contract_id}/progress", { params: { path: { contract_id: saved.id } } }),
        );
        return { saved: progressed, started: true as const };
      } catch (error) {
        return { saved, started: false as const, error };
      }
    },
    onSuccess: ({ saved }) => refresh(saved),
  });
}

export function useUpdateContract(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: ContractUpdate) =>
      unwrap(api.PATCH("/api/v1/admin/contracts/{contract_id}", { params: { path: { contract_id: id } }, body })),
    onSuccess: refresh,
  });
}

export function useAmendContract(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: {
      amended_on: string;
      reason: string;
      changes: AmendmentChanges;
      contract_file_id: string | null;
    }) => {
      await unwrap(
        api.POST("/api/v1/admin/contracts/{contract_id}/amendments", { params: { path: { contract_id: id } }, body }),
      );
      return unwrap(api.GET("/api/v1/admin/contracts/{contract_id}", { params: { path: { contract_id: id } } }));
    },
    onSuccess: refresh,
  });
}

/** 다음 단계 (A109③·A113): 진행(계약서 원본) · 계약 완료(서명된 계약서) · 종료 */
export type StepAction = "progress" | "sign" | "end";
export type StepInput =
  { action: "progress"; fileId: string | null } | { action: "sign"; signedFileId: string } | { action: "end" };

export function useStepContract(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (input: StepInput) => {
      const params = { path: { contract_id: id } };
      if (input.action === "progress")
        return unwrap(
          api.POST("/api/v1/admin/contracts/{contract_id}/progress", {
            params,
            body: input.fileId ? { contract_file_id: input.fileId } : {},
          }),
        );
      if (input.action === "sign")
        return unwrap(
          api.POST("/api/v1/admin/contracts/{contract_id}/sign", {
            params,
            body: { signed_contract_file_id: input.signedFileId },
          }),
        );
      return unwrap(api.POST("/api/v1/admin/contracts/{contract_id}/end", { params }));
    },
    onSuccess: refresh,
  });
}

/** 서명된 계약서 다운로드 주소 (A113) */
export async function signedContractFileUrl(id: string): Promise<string> {
  const res = await unwrap(
    api.GET("/api/v1/admin/contracts/{contract_id}/file-url", {
      params: { path: { contract_id: id }, query: { signed: true } },
    }),
  );
  return res.url;
}

export function useCancelContract(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: { reason: string; canceled_on: string | null }) =>
      unwrap(api.POST("/api/v1/admin/contracts/{contract_id}/cancel", { params: { path: { contract_id: id } }, body })),
    onSuccess: refresh,
  });
}

export function useTerminateContract(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: { reason: TerminationReason; detail: string | null; terminated_on: string | null }) =>
      unwrap(
        api.POST("/api/v1/admin/contracts/{contract_id}/terminate", { params: { path: { contract_id: id } }, body }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteContract(id: string) {
  const client = useQueryClient();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () =>
      unwrap(api.DELETE("/api/v1/admin/contracts/{contract_id}", { params: { path: { contract_id: id } } })),
    onSuccess: () => {
      client.removeQueries({ queryKey: contractKeys.detail(id) });
      refresh();
    },
  });
}

/** 다른 멘토로 옮기기 (A104) */
export function useMoveContract(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (mentorId: string) =>
      unwrap(
        api.POST("/api/v1/admin/contracts/{contract_id}/link", {
          params: { path: { contract_id: id } },
          body: { mentor_id: mentorId },
        }),
      ),
    onSuccess: refresh,
  });
}
