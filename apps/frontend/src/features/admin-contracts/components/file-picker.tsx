import { useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import { uploadContractFile, type ContractFile } from "../api";
import { contractError, fileSize } from "../labels";

const MAX_BYTES = 10 * 1024 * 1024;

/** 계약서 PDF 고르기 (A26): 고르면 바로 올리고 확정된 파일을 돌려준다 */
export function FilePicker({
  value,
  onChange,
  onUploading,
  removable = true,
  label = "계약서 고르기",
}: {
  value: ContractFile | null;
  onChange: (file: ContractFile | null) => void;
  onUploading?: (uploading: boolean) => void;
  removable?: boolean;
  label?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const onPick = async (e: ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0];
    e.target.value = "";
    if (!picked) return;
    if (picked.type !== "application/pdf" && !picked.name.toLowerCase().endsWith(".pdf")) {
      toast.error("PDF 파일만 올릴 수 있어요.");
      return;
    }
    if (picked.size > MAX_BYTES) {
      toast.error("10MB까지 올릴 수 있어요.");
      return;
    }
    setUploading(true);
    onUploading?.(true);
    try {
      onChange(await uploadContractFile(picked));
    } catch (err) {
      toast.error(contractError(err));
    } finally {
      setUploading(false);
      onUploading?.(false);
    }
  };
  return (
    <div className="flex items-center gap-2">
      <span className="min-w-0 flex-1 truncate font-normal">
        {value ? (
          `${value.file_name} · ${fileSize(value.file_size)}`
        ) : (
          <span className="text-muted-foreground">없음</span>
        )}
      </span>
      <Button type="button" variant="outline" size="sm" disabled={uploading} onClick={() => ref.current?.click()}>
        {uploading ? <Spinner className="size-4" /> : null}
        {value ? "다른 파일" : "파일 고르기"}
      </Button>
      {value && removable ? (
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange(null)}>
          빼기
        </Button>
      ) : null}
      <input
        ref={ref}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        tabIndex={-1}
        aria-label={label}
        onChange={(e) => void onPick(e)}
      />
    </div>
  );
}
