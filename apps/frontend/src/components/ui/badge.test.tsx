import { render, screen } from "@testing-library/react";

import { Badge } from "./badge";

describe("Badge", () => {
  it("기본은 accent 배지다", () => {
    render(<Badge>승인 대기</Badge>);
    expect(screen.getByText("승인 대기")).toHaveClass("bg-accent", "text-accent-foreground", "rounded-full");
  });

  it.each([
    ["success", "bg-success-subtle", "text-success-text"],
    ["warning", "bg-warning-subtle", "text-warning-text"],
    ["destructive", "bg-destructive-subtle", "text-destructive-text"],
  ] as const)("%s는 subtle 배경과 상태 글자 색을 쓴다", (variant, bg, fg) => {
    render(<Badge variant={variant}>상태</Badge>);
    expect(screen.getByText("상태")).toHaveClass(bg, fg);
  });
});
