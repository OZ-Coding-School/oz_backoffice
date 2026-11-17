import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Input } from "./input";

describe("Input", () => {
  it("입력을 받는다", async () => {
    render(<Input aria-label="이름" />);
    const input = screen.getByRole("textbox", { name: "이름" });
    await userEvent.type(input, "가수강");
    expect(input).toHaveValue("가수강");
  });

  it("오류는 aria-invalid로 표시한다", () => {
    render(<Input aria-label="이메일" aria-invalid />);
    expect(screen.getByRole("textbox", { name: "이메일" })).toBeInvalid();
  });

  it("비활성이면 입력할 수 없다", async () => {
    render(<Input aria-label="코드" disabled />);
    const input = screen.getByRole("textbox", { name: "코드" });
    await userEvent.type(input, "123");
    expect(input).toHaveValue("");
  });
});
