import { tabCount } from "./api";
import { balanceLine, canceledTail, cancelState, kindLabel, slotLabel } from "./labels";
import { makeRequest } from "./test-utils";

describe("신청 표시 규칙", () => {
  it("탭 건수는 상태별 건수를 더한다 (반려·취소는 둘을 합친다)", () => {
    const counts = { PENDING: 2, APPROVED: 1, REJECTED: 1, CANCELED: 3 };
    expect(["all", "pending", "approved", "closed"].map((t) => tabCount(t as never, counts))).toEqual([7, 2, 1, 4]);
  });

  it("차감 상태 한 줄 (팀 신청은 팀 계좌)", () => {
    expect(balanceLine(makeRequest())).toBe("차감 예정 1시간");
    expect(balanceLine(makeRequest({ team_id: "t1", balance: { state: "HELD", minutes: 90 } }))).toBe(
      "팀 계좌 차감 예정 1시간 30분",
    );
    expect(balanceLine(makeRequest({ balance: { state: "USED", minutes: 30 } }))).toBe("30분 차감");
    expect(balanceLine(makeRequest({ balance: { state: "RETURNED", minutes: 60 } }))).toBe("시간 돌려받음");
    expect(balanceLine(makeRequest({ balance: { state: "NONE", minutes: 0 } }))).toBeNull();
  });

  it("종류·일시 (Asia/Seoul)", () => {
    expect(kindLabel(makeRequest())).toBe("1:1 멘토링");
    expect(kindLabel(makeRequest({ team_id: "t1", team_label: "3팀 알파" }))).toBe("팀 멘토링 · 3팀 알파");
    expect(slotLabel("2026-11-24T10:00:00Z", 60)).toBe("11/24(화) 19:00 ~ 20:00");
  });

  it("취소 주체: 본인·신청자 이름·멘토·운영진·자동, 없으면 시각만", () => {
    const at = { canceled_at: "2026-11-06T03:30:00Z" };
    expect(canceledTail(makeRequest({ ...at, canceled_by: "REQUESTER" }), true)).toBe("11/06 12:30 본인 취소");
    expect(canceledTail(makeRequest({ ...at, canceled_by: "REQUESTER", requester_name: "나수강" }), false)).toBe(
      "11/06 12:30 나수강 취소",
    );
    expect(canceledTail(makeRequest({ ...at, canceled_by: "MENTOR" }), true)).toBe("11/06 12:30 멘토 취소");
    expect(canceledTail(makeRequest({ ...at, canceled_by: "STAFF" }), true)).toBe("11/06 12:30 운영진 취소");
    expect(canceledTail(makeRequest({ ...at, canceled_by: "SYSTEM" }), true)).toBe("11/06 12:30 자동 취소");
    expect(canceledTail(makeRequest({ ...at, canceled_by: null }), true)).toBe("11/06 12:30 취소");
    expect(canceledTail(makeRequest(), true)).toBeNull();
  });

  it("취소 가능: 신청자만, 대기는 언제든, 승인은 시작 N시간 전까지(같은 시각 포함)", () => {
    const session = { id: "s1", starts_at: "2026-11-24T10:00:00Z", ends_at: "2026-11-24T11:00:00Z" };
    const approved = makeRequest({ status: "APPROVED", session });
    const deadline = new Date("2026-11-23T10:00:00Z");
    expect(cancelState(makeRequest(), { mine: false, minLeadHours: 24, now: deadline })).toEqual({ kind: "none" });
    expect(cancelState(makeRequest(), { mine: true, minLeadHours: undefined, now: deadline })).toEqual({
      kind: "available",
      deadline: null,
    });
    expect(cancelState(approved, { mine: true, minLeadHours: 24, now: deadline })).toEqual({
      kind: "available",
      deadline,
    });
    expect(cancelState(approved, { mine: true, minLeadHours: 24, now: new Date(deadline.getTime() + 1000) })).toEqual({
      kind: "deadline_passed",
    });
    expect(cancelState(approved, { mine: true, minLeadHours: undefined, now: deadline })).toEqual({ kind: "none" });
    expect(cancelState(makeRequest({ status: "CANCELED" }), { mine: true, minLeadHours: 24, now: deadline })).toEqual({
      kind: "none",
    });
  });
});
