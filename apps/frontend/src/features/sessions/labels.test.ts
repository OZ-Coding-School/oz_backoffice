import { makeCompleted, makeSession } from "./test-utils";
import { balanceNote, cancelNote, timeBlock } from "./labels";

describe("진행 기록 표시 (F33)", () => {
  it("완료는 실제 진행과 기록 분, 그 밖은 예약 일시와 신청 분을 왼쪽에 둔다", () => {
    expect(timeBlock(makeCompleted())).toEqual({
      label: "실제 진행",
      day: "11/16(월)",
      range: "10:02 ~ 11:01",
      note: "59분 · 기록 60분",
    });
    expect(timeBlock(makeCompleted({ actual_started_at: null, actual_ended_at: null }))).toEqual({
      label: "예약 일시",
      day: "11/16(월)",
      range: "10:00 ~ 11:00",
      note: "기록 60분",
    });
    expect(timeBlock(makeSession())).toMatchObject({ label: "예약 일시", range: "14:00 ~ 15:00", note: "60분" });
  });

  it("차감 상태: 예정·돌려받음, 완료는 신청 시간과 비교한다", () => {
    expect(balanceNote(makeSession())).toBe("차감 예정 1시간");
    expect(balanceNote(makeSession({ team_id: "t1", team_label: "3팀" }))).toBe("팀 계좌 차감 예정 1시간");
    expect(balanceNote(makeSession({ status: "CANCELED", balance: { state: "RETURNED", minutes: 60 } }))).toBe(
      "시간 돌려받음",
    );
    expect(balanceNote(makeCompleted())).toBe("1시간 차감 · 추가 차감 없음");
    expect(balanceNote(makeCompleted({ balance: { state: "USED", minutes: 90 } }))).toBe(
      "1시간 30분 차감 · 추가 30분 포함",
    );
    expect(balanceNote(makeCompleted({ balance: { state: "USED", minutes: 30 } }))).toBe("30분 차감 · 30분 돌려받음");
    expect(balanceNote(makeSession({ balance: { state: "NONE", minutes: 0 } }))).toBeNull();
  });

  it("취소 안내는 사유·시각·주체·돌려받음을 보여 준다", () => {
    const canceled = makeSession({
      status: "CANCELED",
      cancel_reason: "개인 일정으로 참석이 어려워요",
      canceled_at: "2026-11-04T23:10:00Z",
      canceled_by: "REQUESTER",
      balance: { state: "RETURNED", minutes: 60 },
    });
    expect(cancelNote(canceled, true)).toBe(
      "취소 사유 · 개인 일정으로 참석이 어려워요 (11/05 08:10 본인 취소, 시간 돌려받음)",
    );
    expect(cancelNote({ ...canceled, canceled_by: "MENTOR" }, false)).toBe(
      "취소 사유 · 개인 일정으로 참석이 어려워요 (11/05 08:10 멘토 취소, 시간 돌려받음)",
    );
    expect(cancelNote(makeSession(), true)).toBeNull();
  });
});
