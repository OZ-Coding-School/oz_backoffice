import { createFileRoute } from "@tanstack/react-router";

import { holidaysQuery } from "@/features/admin-holidays/api";
import { isDateKey, kstYear } from "@/features/admin-holidays/calendar";
import { HolidaysPage, type HolidaysSearch } from "@/features/admin-holidays/components/holidays-page";

/** 설정 > 공휴일 (F72). 연도 `year`(없으면 올해), 고른 날 `date`(YYYY-MM-DD) */
export const Route = createFileRoute("/_staff/admin/settings/holidays")({
  validateSearch: (search: Record<string, unknown>): HolidaysSearch => {
    const out: HolidaysSearch = {};
    const year = Number(search.year);
    if (Number.isInteger(year) && year >= 2000 && year <= 2100) out.year = year;
    if (typeof search.date === "string" && isDateKey(search.date)) out.date = search.date;
    return out;
  },
  loaderDeps: ({ search }) => ({ year: search.year }),
  loader: ({ context, deps }) => context.queryClient.prefetchQuery(holidaysQuery(deps.year ?? kstYear())),
  component: function Holidays() {
    return <HolidaysPage search={Route.useSearch()} />;
  },
});
