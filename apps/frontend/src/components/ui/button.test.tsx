import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Button } from "./button";

describe("Button", () => {
  it("기본은 Primary·md이고 폼 제출을 하지 않는 type=button이다", () => {
    render(<Button>저장</Button>);
    const button = screen.getByRole("button", { name: "저장" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveClass("bg-primary", "h-9", "text-body-strong");
  });

  it("variant·size에 맞는 토큰 클래스를 쓴다", () => {
    render(
      <Button variant="destructive" size="sm" type="submit">
        삭제
      </Button>,
    );
    const button = screen.getByRole("button", { name: "삭제" });
    expect(button).toHaveAttribute("type", "submit");
    expect(button).toHaveClass("bg-destructive", "h-8", "text-label");
  });

  it("비활성이면 누를 수 없다", async () => {
    const onClick = vi.fn<() => void>();
    render(
      <Button disabled onClick={onClick}>
        승인
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "승인" }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("asChild면 자식 요소에 스타일을 입힌다", () => {
    render(
      <Button asChild variant="outline">
        <a href="/login">로그인</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "로그인" });
    expect(link).not.toHaveAttribute("type");
    expect(link).toHaveClass("border-input");
  });
});
