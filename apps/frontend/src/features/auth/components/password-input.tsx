import { Eye, EyeOff, Lock } from "lucide-react";
import { useState, type ComponentProps } from "react";

import { InputIcon } from "@/components/form-field";
import { Input } from "@/components/ui/input";

/** 비밀번호 칸 (Figma: 자물쇠 아이콘 + 오른쪽 보기 버튼). */
export function PasswordInput(props: Omit<ComponentProps<typeof Input>, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <InputIcon icon={Lock} />
      <Input type={visible ? "text" : "password"} className="pr-10 pl-9" {...props} />
      <button
        type="button"
        aria-label={visible ? "비밀번호 숨기기" : "비밀번호 보기"}
        aria-pressed={visible}
        disabled={props.disabled}
        onClick={() => setVisible((v) => !v)}
        className="absolute top-1/2 right-2 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-foreground outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        {visible ? <EyeOff aria-hidden className="size-4" /> : <Eye aria-hidden className="size-4" />}
      </button>
    </div>
  );
}
