import { render, screen } from "@testing-library/react";

import { Badge } from "./badge";

describe("Badge", () => {
  it("기본은 accent 배지다", () => {
    render(<Badge>승인 대기</Badge>);
    expect(screen.getByText("승인 대기")).toHaveClass("bg-accent", "text-accent-foreground", "rounded-full");
  });

  it.each([
    ["success", "bg-success/15", "text-success-text", "ring-success/35"],
    ["warning", "bg-warning/20", "text-warning-text", "ring-warning/45"],
    ["destructive", "bg-destructive/15", "text-destructive-text", "ring-destructive/35"],
  ] as const)("%s는 진한 파스텔 바탕·같은 색 테두리와 상태 글자 색을 쓴다 (F97)", (variant, bg, fg, ring) => {
    render(<Badge variant={variant}>상태</Badge>);
    expect(screen.getByText("상태")).toHaveClass(bg, fg, ring);
  });
});
