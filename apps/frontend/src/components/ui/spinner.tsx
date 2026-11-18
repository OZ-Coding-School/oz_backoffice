import { LoaderCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export function Spinner({ className, label = "불러오는 중" }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-label={label} className={cn("inline-flex text-primary", className)}>
      <LoaderCircle aria-hidden className="size-6 animate-spin" />
    </span>
  );
}
