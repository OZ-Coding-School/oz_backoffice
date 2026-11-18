import { formatPhone, isValidPhone, phoneDigits } from "./phone";

describe("휴대폰 번호", () => {
  it("입력하는 대로 하이픈을 넣는다", () => {
    expect(formatPhone("010")).toBe("010");
    expect(formatPhone("0101234")).toBe("010-1234");
    expect(formatPhone("01012345678")).toBe("010-1234-5678");
    expect(formatPhone("0111234567")).toBe("011-123-4567");
    expect(formatPhone("010-1234-56789")).toBe("010-1234-5678");
  });

  it("보낼 때는 숫자만, 01로 시작하는 10~11자리만 받는다", () => {
    expect(phoneDigits("010-1234-5678")).toBe("01012345678");
    expect(isValidPhone("010-1234-5678")).toBe(true);
    expect(isValidPhone("02-123-4567")).toBe(false);
    expect(isValidPhone("010-123")).toBe(false);
  });
});
