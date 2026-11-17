import { CircleCheck } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { MEMBER_BRAND, type BrandCopy } from "../brand";

const PLATFORM = "오즈코딩스쿨 운영 행정 지원 플랫폼";

/** 로고 (OZ 마크 + 플랫폼 이름). 소개 영역에서는 흰 마크, 그 밖에는 보라 마크. */
export function Logo({ onBrand = false, className }: { onBrand?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span
        aria-hidden
        className={cn(
          "inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-caption-strong",
          onBrand ? "bg-white text-primary" : "bg-primary text-primary-foreground",
        )}
      >
        OZ
      </span>
      <span
        className={cn(
          onBrand ? "text-caption-strong text-white lg:text-body-strong" : "text-body-strong text-foreground",
        )}
      >
        {PLATFORM}
      </span>
    </div>
  );
}

/**
 * 로그인·재설정·가입 화면 틀 (Figma `Login`, decisions F21).
 * 소개 영역: 데스크톱(lg) 560, 태블릿(md) 320, 모바일은 숨기고 폼 위에 로고.
 */
export function AuthLayout({ brand = MEMBER_BRAND, children }: { brand?: BrandCopy; children: ReactNode }) {
  return (
    <div className="flex min-h-dvh bg-background">
      <aside className="relative hidden shrink-0 flex-col overflow-hidden bg-brand-panel px-8 py-10 text-white md:flex md:w-80 lg:w-140 lg:px-14 lg:py-12">
        <span aria-hidden className="absolute -top-24 -right-32 size-105 rounded-full bg-white/10" />
        <span aria-hidden className="absolute -bottom-28 -left-36 size-95 rounded-full bg-white/10" />
        <Logo onBrand className="relative" />
        <div className="relative my-auto flex flex-col gap-5">
          <h2 className="text-h1 whitespace-pre-line lg:text-display">{brand.headline}</h2>
          {brand.features?.length ? (
            <ul className="flex flex-col gap-3 text-body-sm lg:text-body">
              {brand.features.map((feature) => (
                <li key={feature} className="flex items-center gap-2.5">
                  <CircleCheck aria-hidden className="size-4 shrink-0" />
                  {feature}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <p className="relative text-caption text-white/70">© 2026 Next Runners · 오즈코딩스쿨</p>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col px-4 pt-5 pb-6 md:items-center md:justify-center md:px-6 md:py-12">
        <Logo className="mb-10 md:hidden" />
        <div className="w-full md:max-w-100">{children}</div>
      </main>
    </div>
  );
}
