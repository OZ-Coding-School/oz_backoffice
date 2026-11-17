import { screen } from "@testing-library/react";

import { renderRoute } from "@/test/render";

describe("디자인 시스템 확인 화면", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("개발 모드에서는 토큰과 컴포넌트를 보여 준다", async () => {
    await renderRoute("/dev/design-system");
    expect(await screen.findByRole("heading", { name: "디자인 시스템" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "테마" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "primary" })).toHaveLength(2); // md·sm
  });

  it("운영 빌드에서는 없는 경로로 처리한다", async () => {
    vi.stubEnv("DEV", false);
    await renderRoute("/dev/design-system");
    expect(await screen.findByRole("heading", { name: "페이지를 찾을 수 없습니다" })).toBeInTheDocument();
  });
});
