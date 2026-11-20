import { accountLabel, accountSummary, deltaText, sortAccounts, typeLabel } from "./labels";
import { makeAccount, tx } from "./test-utils";

describe("시간 내역 표시 (F36·F38)", () => {
  it("변동은 남은 시간 기준이고, 차감은 확정만 보여 준다", () => {
    const at = "2026-11-16T01:02:00Z";
    expect(deltaText(tx("1", "HOLD", 60, 0, "", at))).toBe("−60분");
    expect(deltaText(tx("1", "USING", 60, 0, "", at))).toBe("— · 확정 1시간");
    expect(deltaText(tx("1", "RELEASE", 60, 0, "", at))).toBe("+60분");
    expect(deltaText(tx("1", "REFUND", 30, 0, "", at))).toBe("+30분");
    expect(deltaText(tx("1", "OVERTIME", 30, 0, "", at))).toBe("−30분");
    expect(deltaText(tx("1", "STAFF_GRANT", 120, 0, "", at))).toBe("+120분");
    expect(deltaText(tx("1", "STAFF_ADJUST", -60, 0, "", at))).toBe("−60분");
  });

  it("유형은 사용자 용어, 음수 조정은 회수", () => {
    expect(typeLabel({ type: "HOLD", amount: 60 }).label).toBe("차감 예정");
    expect(typeLabel({ type: "RELEASE", amount: 60 }).label).toBe("차감 예정 취소");
    expect(typeLabel({ type: "USING", amount: 60 }).label).toBe("차감");
    expect(typeLabel({ type: "REFUND", amount: 60 }).label).toBe("돌려받음");
    expect(typeLabel({ type: "OVERTIME", amount: 60 }).label).toBe("추가 차감");
    expect(typeLabel({ type: "STAFF_ADJUST", amount: 60 }).label).toBe("조정");
    expect(typeLabel({ type: "STAFF_ADJUST", amount: -60 }).label).toBe("회수");
  });

  it("계좌 이름·요약과 순서(사용 중 1:1 → 팀 → 만료)", () => {
    const one = makeAccount();
    const team = makeAccount({ id: "a2", owner_type: "TEAM", owner_name: "3팀 알파" });
    const old = makeAccount({ id: "a0", is_expired: true });
    expect(accountLabel(team)).toBe("3팀 알파 계좌");
    expect(accountSummary(one)).toBe("차감 예정 1시간 · 사용 1시간 30분 · 01/31까지");
    expect(sortAccounts([old, team, one]).map((a) => a.id)).toEqual(["a1", "a2", "a0"]);
  });
});
