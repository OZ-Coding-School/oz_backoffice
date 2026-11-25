import { Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { errorText, eul } from "@/features/admin-org/text";
import { cn } from "@/lib/utils";

import { useCreateHoliday, useDeleteHoliday, type Holiday } from "../api";
import { longLabel, shortLabel, weekday } from "../calendar";

const NAME_MAX = 50;

/** 선택한 날 칸 (F72): 구분·이름·삭제 가능 여부만, 평일이면 등록 폼, 추가 휴일이면 삭제 */
export function DayPanel({
  date,
  holidays,
  custom,
  year,
  canManage,
}: {
  date: string;
  holidays: Holiday[];
  custom: Holiday[];
  year: number;
  canManage: boolean;
}) {
  const customDay = holidays.find((h) => h.source === "CUSTOM");
  const publicDay = holidays.filter((h) => h.source === "PUBLIC");
  return (
    <section
      aria-label="선택한 날"
      className="sticky top-6 flex flex-col overflow-hidden rounded-xl border border-border bg-card"
    >
      <div className="flex flex-col gap-0.5 border-b border-border bg-muted px-4 py-3">
        <span className="text-caption text-muted-foreground">선택한 날</span>
        <h3 className="text-body-strong text-foreground">{longLabel(date)}</h3>
      </div>
      <div className="flex flex-col gap-3 p-4">
        <dl className="flex flex-col gap-2.5">
          {publicDay.length ? (
            <>
              <Row label="구분">
                <span className="text-destructive-text">법정공휴일</span>
              </Row>
              <Row label="이름">{publicDay.map((h) => h.name).join(", ")}</Row>
              {customDay ? <Row label="추가 휴일">{customDay.name}</Row> : null}
              <Row label="삭제">{customDay ? "추가 휴일만 가능" : "불가"}</Row>
            </>
          ) : customDay ? (
            <>
              <Row label="구분">
                <span className="text-primary-text">추가 휴일</span>
              </Row>
              <Row label="이름">{customDay.name}</Row>
              <Row label="삭제">가능</Row>
            </>
          ) : (
            <Row label="구분">{weekday(date) === 0 || weekday(date) === 6 ? "주말" : "평일"}</Row>
          )}
        </dl>
        {canManage && customDay ? <DeleteButton holiday={customDay} /> : null}
        {canManage && !holidays.length ? <AddForm key={date} date={date} /> : null}
      </div>
      <div className="flex flex-col gap-2 border-t border-border p-4">
        <h4 className="text-caption text-muted-foreground">{year}년 추가 휴일</h4>
        <HolidayList label={`${year}년 추가 휴일`} year={year} items={custom} empty="등록한 추가 휴일이 없어요." />
      </div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline gap-2">
      <dt className="w-14 shrink-0 text-caption text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-body-strong text-foreground">{children}</dd>
    </div>
  );
}

/** 공휴일 목록: 날짜순, 점 색으로 법정(빨강)·추가(보라). 누르면 그날을 고른다 */
export function HolidayList({
  label,
  year,
  items,
  empty,
}: {
  label: string;
  year: number;
  items: Holiday[];
  empty: string;
}) {
  if (!items.length) return <p className="text-caption text-muted-foreground">{empty}</p>;
  return (
    <ul aria-label={label} className="flex flex-col gap-1">
      {items.map((h) => (
        <li key={`${h.source}-${h.holiday_date}-${h.name}`}>
          <Link
            to="/admin/settings/holidays"
            search={{ year, date: h.holiday_date }}
            className="flex items-center gap-2 rounded-md px-1 py-1 outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span
              aria-hidden
              className={cn("size-2 shrink-0 rounded-full", h.source === "PUBLIC" ? "bg-destructive" : "bg-primary")}
            />
            <span className="min-w-0 flex-1 truncate text-label text-foreground">{h.name}</span>
            <span className="text-caption text-muted-foreground">{shortLabel(h.holiday_date)}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function AddForm({ date }: { date: string }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | undefined>();
  const create = useCreateHoliday();
  const onSubmit = async () => {
    setError(undefined);
    try {
      await create.mutateAsync({ holiday_date: date, name });
      toast.success(`${shortLabel(date)} ${eul(name.trim())} 추가 휴일로 등록했어요`);
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        void onSubmit();
      }}
    >
      <FormField label="휴일 이름" error={error}>
        {(props) => (
          <Input
            {...props}
            placeholder="예: 창립기념일"
            maxLength={NAME_MAX}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        )}
      </FormField>
      <Button type="submit" disabled={create.isPending || !name.trim()}>
        추가 휴일로 등록
      </Button>
    </form>
  );
}

function DeleteButton({ holiday }: { holiday: Holiday }) {
  const [open, setOpen] = useState(false);
  const remove = useDeleteHoliday();
  const [error, setError] = useState<string | null>(null);
  const onConfirm = async () => {
    if (!holiday.id) return;
    setError(null);
    try {
      await remove.mutateAsync(holiday.id);
      toast.success(`${eul(holiday.name)} 지웠어요`);
      setOpen(false);
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <>
      <Button
        variant="outline"
        className="border-destructive-text text-destructive-text hover:bg-destructive-subtle hover:text-destructive-text"
        onClick={() => setOpen(true)}
      >
        추가 휴일 삭제
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
          <DialogTitle className="pr-8 text-h2 text-foreground">{eul(holiday.name)} 지울까요?</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            {longLabel(holiday.holiday_date)}은 공휴일에서 빠져요.
          </DialogDescription>
          {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              취소
            </Button>
            <Button variant="destructive" disabled={remove.isPending} onClick={() => void onConfirm()}>
              삭제
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
