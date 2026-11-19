import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Inbox } from "lucide-react";

import { EmptyState } from "./empty-state";
import { ErrorState } from "./error-state";

describe("공통 상태 조각 (F27)", () => {
  it("빈 상태는 제목과 설명을 보여 준다", () => {
    render(<EmptyState icon={Inbox} title="신청이 없어요" description="새 신청이 오면 여기에 보여요." />);
    expect(screen.getByRole("heading", { name: "신청이 없어요" })).toBeInTheDocument();
    expect(screen.getByText("새 신청이 오면 여기에 보여요.")).toBeInTheDocument();
  });

  it("오류 상태는 알림으로 읽히고 다시 시도를 누를 수 있다", async () => {
    const retry = vi.fn<() => void>();
    render(<ErrorState onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("불러오지 못했어요");
    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
