import { createFileRoute, notFound } from "@tanstack/react-router";
import { Mail, Plus, Search } from "lucide-react";
import type { ReactNode } from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { setThemePreference, useTheme, type ThemePreference } from "@/lib/theme";
import { cn } from "@/lib/utils";

/** 디자인 토큰·기본 컴포넌트 확인 화면. 개발 서버에서만 열린다 (decisions F18). */
export const Route = createFileRoute("/dev/design-system")({
  beforeLoad: () => {
    if (!import.meta.env.DEV) throw notFound();
  },
  component: DesignSystem,
});

const COLOR_GROUPS: { title: string; tokens: string[] }[] = [
  {
    title: "기본",
    tokens: ["background", "foreground", "card", "popover", "muted", "muted-foreground", "border", "input", "ring"],
  },
  {
    title: "브랜드",
    tokens: [
      "primary",
      "primary-hover",
      "primary-foreground",
      "primary-text",
      "secondary",
      "accent",
      "accent-foreground",
      "brand-panel",
    ],
  },
  {
    title: "상태",
    tokens: [
      "destructive",
      "destructive-subtle",
      "destructive-text",
      "success",
      "success-subtle",
      "success-text",
      "warning",
      "warning-subtle",
      "warning-text",
      "info",
      "info-subtle",
      "info-text",
    ],
  },
  {
    title: "사이드바",
    tokens: ["sidebar", "sidebar-foreground", "sidebar-accent", "sidebar-accent-foreground", "sidebar-border"],
  },
];

const TEXT_STYLES: { className: string; label: string }[] = [
  { className: "text-display", label: "Display 30/38 Bold" },
  { className: "text-h1", label: "Heading/H1 24/32 Bold" },
  { className: "text-h2", label: "Heading/H2 20/28 Bold" },
  { className: "text-h3", label: "Heading/H3 16/24 Bold" },
  { className: "text-body-lg", label: "Body/Large 16/24" },
  { className: "text-body", label: "Body/Default 14/20" },
  { className: "text-body-strong", label: "Body/Strong 14/20 Medium" },
  { className: "text-body-sm", label: "Body/Small 13/18" },
  { className: "text-label", label: "Label/Default 13/18 Medium" },
  { className: "text-caption", label: "Caption 12/16" },
  { className: "text-caption-strong", label: "Caption/Strong 12/16 Medium" },
];

const BUTTON_VARIANTS: NonNullable<ButtonProps["variant"]>[] = [
  "primary",
  "secondary",
  "outline",
  "ghost",
  "destructive",
  "link",
];
const BADGE_VARIANTS: NonNullable<BadgeProps["variant"]>[] = [
  "default",
  "primary",
  "secondary",
  "outline",
  "success",
  "warning",
  "info",
  "destructive",
];
const THEMES: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "시스템" },
  { value: "light", label: "라이트" },
  { value: "dark", label: "다크" },
];

function DesignSystem() {
  const { preference, resolved } = useTheme();
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-10 px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-h1">디자인 시스템</h1>
          <p className="text-body-sm text-muted-foreground">Figma `Design System`·`Components` 토큰 확인 (개발 전용)</p>
        </div>
        <div role="group" aria-label="테마" className="flex gap-1 rounded-lg border border-border p-1">
          {THEMES.map((theme) => (
            <Button
              key={theme.value}
              size="sm"
              variant={preference === theme.value ? "secondary" : "ghost"}
              aria-pressed={preference === theme.value}
              onClick={() => setThemePreference(theme.value)}
            >
              {theme.label}
            </Button>
          ))}
          <span className="self-center px-2 text-caption text-muted-foreground">적용: {resolved}</span>
        </div>
      </header>

      <Section title="색">
        {COLOR_GROUPS.map((group) => (
          <div key={group.title} className="flex flex-col gap-2">
            <h3 className="text-label text-muted-foreground">{group.title}</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {group.tokens.map((token) => (
                <div key={token} className="flex flex-col gap-1">
                  <div className="h-12 rounded-lg border border-border" style={{ background: `var(--${token})` }} />
                  <code className="font-mono text-caption">{token}</code>
                </div>
              ))}
            </div>
          </div>
        ))}
      </Section>

      <Section title="글자">
        {TEXT_STYLES.map((style) => (
          <div
            key={style.className}
            className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-2"
          >
            <span className={style.className}>오즈코딩스쿨 운영 행정 지원 플랫폼</span>
            <code className="font-mono text-caption text-muted-foreground">
              {style.className} · {style.label}
            </code>
          </div>
        ))}
        <p className="font-mono text-body">Fira Code 19:00 ~ 20:00 · const x = 1;</p>
      </Section>

      <Section title="그림자·모서리">
        <div className="flex flex-wrap gap-6">
          {["shadow-sm", "shadow-md", "shadow-lg"].map((shadow) => (
            <div key={shadow} className={cn("flex h-20 w-32 items-center justify-center rounded-xl bg-card", shadow)}>
              <code className="font-mono text-caption">{shadow}</code>
            </div>
          ))}
          {["rounded-sm", "rounded-md", "rounded-lg", "rounded-xl", "rounded-full"].map((radius) => (
            <div key={radius} className={cn("flex h-20 w-24 items-center justify-center bg-accent", radius)}>
              <code className="font-mono text-caption text-accent-foreground">{radius}</code>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Button">
        {(["md", "sm"] as const).map((size) => (
          <div key={size} className="flex flex-wrap items-center gap-3">
            {BUTTON_VARIANTS.map((variant) => (
              <Button key={variant} variant={variant} size={size}>
                {variant}
              </Button>
            ))}
            <Button size={size} disabled>
              disabled
            </Button>
            <Button size={size}>
              <Plus />
              아이콘
            </Button>
          </div>
        ))}
      </Section>

      <Section title="Badge">
        <div className="flex flex-wrap gap-2">
          {BADGE_VARIANTS.map((variant) => (
            <Badge key={variant} variant={variant}>
              {variant}
            </Badge>
          ))}
        </div>
      </Section>

      <Section title="Input">
        <div className="grid max-w-xl gap-4 sm:grid-cols-2">
          <Input aria-label="기본" placeholder="내용을 입력하세요" />
          <Input aria-label="값" defaultValue="입력한 값" />
          <Input aria-label="오류" aria-invalid defaultValue="잘못된 값" />
          <Input aria-label="비활성" disabled placeholder="비활성" />
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input aria-label="검색" className="pl-9" placeholder="이름으로 검색" />
          </div>
          <div className="relative">
            <Mail className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input aria-label="이메일" type="email" className="pl-9" placeholder="name@gmail.com" />
          </div>
        </div>
      </Section>
    </main>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-h2">{title}</h2>
      {children}
    </section>
  );
}
