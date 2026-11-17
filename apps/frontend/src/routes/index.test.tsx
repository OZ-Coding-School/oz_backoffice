import { screen } from "@testing-library/react";

import { renderRoute } from "@/test/render";

describe("홈", () => {
  it("플랫폼 이름을 보여 준다", async () => {
    await renderRoute("/");
    expect(await screen.findByRole("heading", { name: "오즈코딩스쿨 운영 행정 지원 플랫폼" })).toBeInTheDocument();
  });

  it("없는 경로는 안내를 보여 준다", async () => {
    await renderRoute("/없는-경로");
    expect(await screen.findByRole("heading", { name: "페이지를 찾을 수 없습니다" })).toBeInTheDocument();
  });
});
