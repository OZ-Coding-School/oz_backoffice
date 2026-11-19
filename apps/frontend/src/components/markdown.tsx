import { lazy, Suspense, type ComponentProps } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

const CodeBlock = lazy(() => import("./code-block"));

/**
 * 공용 마크다운 (decisions F4·F16): GFM, HTML 태그는 버리고(렌더링 안 함), 이미지는 막고, 링크는 새 창.
 * 코드 블록 하이라이트(Shiki)는 코드 블록이 있을 때만 불러온다.
 */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("markdown flex flex-col gap-3 text-body text-foreground", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml disallowedElements={["img"]} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

const COMPONENTS: Components = {
  h1: (p) => <h3 className="text-h2" {...strip(p)} />,
  h2: (p) => <h4 className="text-h3" {...strip(p)} />,
  h3: (p) => <h5 className="text-body-strong" {...strip(p)} />,
  h4: (p) => <h6 className="text-body-strong" {...strip(p)} />,
  h5: (p) => <h6 className="text-body-strong" {...strip(p)} />,
  h6: (p) => <h6 className="text-body-strong" {...strip(p)} />,
  p: (p) => <p {...strip(p)} />,
  ul: (p) => <ul className="flex list-disc flex-col gap-1 pl-5" {...strip(p)} />,
  ol: (p) => <ol className="flex list-decimal flex-col gap-1 pl-5" {...strip(p)} />,
  blockquote: (p) => <blockquote className="border-l-2 border-border pl-3 text-muted-foreground" {...strip(p)} />,
  a: ({ node: _node, ...p }) => (
    <a className="text-primary-text underline underline-offset-4" target="_blank" rel="noopener noreferrer" {...p} />
  ),
  table: (p) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body-sm" {...strip(p)} />
    </div>
  ),
  th: (p) => <th className="border border-border bg-muted px-2 py-1 text-left text-label" {...strip(p)} />,
  td: (p) => <td className="border border-border px-2 py-1" {...strip(p)} />,
  pre: ({ children }) => <>{children}</>,
  code: ({ node: _node, className, children, ...p }) => {
    const lang = /language-([\w-]+)/.exec(className ?? "")?.[1];
    const text = String(children ?? "");
    if (!lang && !text.includes("\n")) {
      return (
        <code className="rounded-sm bg-muted px-1 py-0.5 font-mono text-body-sm" {...p}>
          {children}
        </code>
      );
    }
    const code = text.replace(/\n$/, "");
    return (
      <Suspense fallback={<PlainCode code={code} />}>
        <CodeBlock code={code} lang={lang} />
      </Suspense>
    );
  },
};

function strip<T extends { node?: unknown }>({ node: _node, ...rest }: T): Omit<T, "node"> {
  return rest;
}

export function PlainCode({ code, ...props }: { code: string } & ComponentProps<"pre">) {
  return (
    <pre
      className="overflow-x-auto rounded-md border border-border bg-background px-3 py-2 font-mono text-body-sm"
      {...props}
    >
      <code>{code}</code>
    </pre>
  );
}
