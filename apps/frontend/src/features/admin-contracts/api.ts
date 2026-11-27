import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { postPhoto } from "@/features/mentor-profile/api";

export type Contract = components["schemas"]["ContractResponse"];
export type ContractStatus = components["schemas"]["ContractStatus"];
export type ContractType = components["schemas"]["ContractType"];
/** 이 화면이 아직 다루는 종류 (A109 화면 개편 전) */
export type EducatorType = Extract<ContractType, "MENTOR" | "INSTRUCTOR">;
export type ContractFile = components["schemas"]["ContractFileResponse"];
export type ManagerCandidate = components["schemas"]["ManagerCandidateResponse"];
export type ContractFields = components["schemas"]["ContractFields"];
export type ContractUpdate = components["schemas"]["ContractUpdate"];

export const PAGE_SIZE = 20;

export interface ContractFilter {
  status?: ContractStatus;
  type?: EducatorType;
  q?: string;
  mentorId?: string;
}

export const contractKeys = {
  all: ["admin-contracts"] as const,
  list: (f: ContractFilter) =>
    ["admin-contracts", "list", f.status ?? "", f.type ?? "", f.q ?? "", f.mentorId ?? ""] as const,
  detail: (id: string) => ["admin-contracts", "detail", id] as const,
  managers: (q: string) => ["admin-contracts", "managers", q] as const,
};

/** 계약 목록 (A25·A103). 20개씩 이어 붙인다. 최근 등록부터 */
export function contractsQuery(f: ContractFilter) {
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
              ...(f.status ? { status: [f.status] } : {}),
              ...(f.type ? { contract_type: [f.type] } : {}),
              ...(f.q ? { q: f.q } : {}),
              ...(f.mentorId ? { mentor_id: f.mentorId } : {}),
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

/** 계약이 바뀌면 그 계약·목록·멘토(계약 수·가입 전 멘토)를 다시 읽는다 */
function useRefresh() {
  const client = useQueryClient();
  return (contract?: Contract) => {
    if (contract) client.setQueryData(contractKeys.detail(contract.id), contract);
    void client.invalidateQueries({ queryKey: ["admin-contracts", "list"] });
    void client.invalidateQueries({ queryKey: ["admin-mentors"] });
  };
}

export function useCreateContract() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: ContractFields) => unwrap(api.POST("/api/v1/admin/contracts", { body })),
    onSuccess: refresh,
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

export type ContractAction = "confirm" | "terminate";

export function useContractAction(id: string) {
  const refresh = useRefresh();
  return useMutation({
    // A109 화면 개편 전 임시: 확정 = 진행 → 완료, 해지는 합의 해지
    mutationFn: async (action: ContractAction) => {
      const params = { path: { contract_id: id } };
      if (action === "terminate")
        return unwrap(
          api.POST("/api/v1/admin/contracts/{contract_id}/terminate", {
            params,
            body: { reason: "TERMINATED_BY_MUTUAL_AGREEMENT" },
          }),
        );
      await unwrap(api.POST("/api/v1/admin/contracts/{contract_id}/progress", { params }));
      return unwrap(api.POST("/api/v1/admin/contracts/{contract_id}/sign", { params }));
    },
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
