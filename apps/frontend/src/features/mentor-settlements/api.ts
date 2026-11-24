import { queryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type SettlementSummary = components["schemas"]["SettlementSummary"];
export type SettlementDetail = components["schemas"]["SettlementDetail"];
export type SettlementItem = components["schemas"]["SettlementItemResponse"];

export const settlementKeys = {
  all: ["mentor-settlements"] as const,
  list: ["mentor-settlements", "list"] as const,
  detail: (id: string) => ["mentor-settlements", "detail", id] as const,
};

/** 내 정산 (A55·A56): 마감된 정산만, 최근 월부터. 기수 필터는 화면에서 거른다 */
export const mySettlementsQuery = queryOptions({
  queryKey: settlementKeys.list,
  queryFn: () => unwrap(api.GET("/api/v1/me/mentor-settlements")),
});

/** 정산서 명세 (A55·A80) */
export function mySettlementQuery(id: string) {
  return queryOptions({
    queryKey: settlementKeys.detail(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/me/mentor-settlements/{settlement_id}", { params: { path: { settlement_id: id } } })),
  });
}
