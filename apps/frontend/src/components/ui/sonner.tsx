import { CircleCheck, CircleX, Info, TriangleAlert } from "lucide-react";
import { Toaster as Sonner } from "sonner";

import { useTheme } from "@/lib/theme";

/**
 * Figma `Components / Toast` (360폭, popover 배경·border·Shadow/lg, 아이콘 20px 상태 글자 색).
 * 데스크톱·태블릿은 오른쪽 위, 모바일은 위쪽 화면 폭(좌우 16px) (decisions F21).
 */
export function Toaster() {
  const { resolved } = useTheme();
  return (
    <Sonner
      theme={resolved}
      position="top-right"
      offset={24}
      mobileOffset={16}
      closeButton
      icons={{
        success: <CircleCheck className="size-5 text-success-text" />,
        error: <CircleX className="size-5 text-destructive-text" />,
        info: <Info className="size-5 text-info-text" />,
        warning: <TriangleAlert className="size-5 text-warning-text" />,
      }}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "relative flex w-full items-start gap-3 rounded-lg border border-border bg-popover px-4 py-3.5 text-popover-foreground shadow-lg md:w-90",
          title: "text-body-strong",
          description: "text-body-sm text-muted-foreground",
          closeButton:
            "absolute! top-3! right-3! left-auto! size-6! rounded-md! border-0! bg-transparent! text-foreground! hover:bg-accent! transform-none!",
          icon: "mt-px",
        },
      }}
    />
  );
}
