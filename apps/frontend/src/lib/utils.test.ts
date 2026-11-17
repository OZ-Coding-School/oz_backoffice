import { cn } from "./utils";

describe("cn", () => {
  it("토큰 글자 스타일과 글자 색을 둘 다 남긴다", () => {
    expect(cn("text-primary-foreground", "text-body-strong")).toBe("text-primary-foreground text-body-strong");
  });

  it("같은 그룹은 뒤의 것을 남긴다", () => {
    expect(cn("text-body", "text-caption")).toBe("text-caption");
    expect(cn("text-foreground", "text-muted-foreground")).toBe("text-muted-foreground");
  });
});
