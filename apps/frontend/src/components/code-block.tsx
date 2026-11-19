import { useEffect, useState } from "react";
import type { ThemedToken } from "shiki";

import { PlainCode } from "./markdown";

/** Shiki 하이라이트 (F16): 언어 문법은 처음 쓸 때 불러온다. 모르는 언어나 실패하면 그냥 글자로 보여 준다. */
export default function CodeBlock({ code, lang }: { code: string; lang: string | undefined }) {
  const [lines, setLines] = useState<ThemedToken[][] | null>(null);

  useEffect(() => {
    let alive = true;
    if (!lang) return;
    void import("shiki")
      .then(async ({ codeToTokens, bundledLanguages }) => {
        if (!(lang in bundledLanguages)) return;
        const result = await codeToTokens(code, {
          lang: lang as keyof typeof bundledLanguages,
          themes: { light: "github-light", dark: "github-dark" },
        });
        if (alive) setLines(result.tokens);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [code, lang]);

  if (!lines) return <PlainCode code={code} data-lang={lang} />;
  return (
    <pre className="overflow-x-auto rounded-md border border-border bg-background px-3 py-2 font-mono text-body-sm">
      <code>
        {lines.map((line, i) => (
          // 줄은 순서가 바뀌지 않는다
          // oxlint-disable-next-line no-array-index-key
          <span key={i} className="block">
            {line.map((token, j) => (
              // oxlint-disable-next-line no-array-index-key
              <span key={j} className="shiki-token" style={token.htmlStyle as React.CSSProperties}>
                {token.content}
              </span>
            ))}
          </span>
        ))}
      </code>
    </pre>
  );
}
