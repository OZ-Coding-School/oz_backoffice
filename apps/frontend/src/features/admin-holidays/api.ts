import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type Holiday = components["schemas"]["HolidayResponse"];
export type HolidayList = components["schemas"]["HolidayListResponse"];

export const holidayKeys = {
  all: ["admin-holidays"] as const,
  year: (year: number) => ["admin-holidays", year] as const,
};

/** 그해 법정공휴일 + 추가 휴일, 법정공휴일 마지막 동기화 시각 (A95) */
export function holidaysQuery(year: number) {
  return queryOptions({
    queryKey: holidayKeys.year(year),
    queryFn: () => unwrap(api.GET("/api/v1/admin/mentoring-holidays", { params: { query: { year } } })),
  });
}

function useInvalidate() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: holidayKeys.all });
}

/** 추가 휴일 등록 (A34). 같은 날이 있으면 409 `holiday_already_exists` */
export function useCreateHoliday() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { holiday_date: string; name: string }) =>
      unwrap(api.POST("/api/v1/admin/mentoring-holidays", { body: { ...body, name: body.name.trim() } })),
    onSuccess: invalidate,
  });
}

export function useDeleteHoliday() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE("/api/v1/admin/mentoring-holidays/{holiday_id}", { params: { path: { holiday_id: id } } })),
    onSuccess: invalidate,
  });
}

/** 올해·내년 법정공휴일을 지금 받는다 (A95). 실패하면 503 `holiday_sync_failed` */
export function useSyncHolidays() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/admin/mentoring-holidays/sync")),
    onSuccess: invalidate,
  });
}
