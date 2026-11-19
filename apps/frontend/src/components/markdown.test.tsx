import { render, screen } from "@testing-library/react";

import { Markdown } from "./markdown";

describe("공용 마크다운 (F4)", () => {
  it("GFM을 보여 주고, 링크는 새 창, 이미지와 HTML 태그는 보여 주지 않는다", () => {
    const { container } = render(
      <Markdown>
        {
          "## 제목\n\n- 항목\n- [x] 완료\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\n[문서](https://example.com) ![사진](https://example.com/a.png)\n\n<b>굵게</b> `코드`"
        }
      </Markdown>,
    );
    expect(screen.getByRole("heading", { name: "제목" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByRole("table")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "문서" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText("코드").tagName).toBe("CODE");
  });

  it("코드 블록은 하이라이트 전에도 글자로 보여 준다", () => {
    render(<Markdown>{"```python\nprint(1)\n```"}</Markdown>);
    expect(screen.getByText("print(1)")).toBeInTheDocument();
  });
});
