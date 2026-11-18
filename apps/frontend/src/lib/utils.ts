import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * 디자인 토큰의 글자 스타일(`text-h1`, `text-body-strong` …)을 글자 크기로 알려 준다.
 * 알려 주지 않으면 tailwind-merge가 색(`text-primary-foreground`)과 같은 그룹으로 보고 하나를 지운다.
 */
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: [
        "display",
        "h1",
        "h2",
        "h3",
        "body-lg",
        "body",
        "body-strong",
        "body-sm",
        "label",
        "caption",
        "caption-strong",
      ],
    },
  },
});

/** 조건부 클래스 이름을 합치고, 겹치는 Tailwind 클래스는 뒤의 것을 남긴다. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
