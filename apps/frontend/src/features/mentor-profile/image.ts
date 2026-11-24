/** 사진 원본으로 고를 수 있는 형식과 크기 (서버는 줄인 결과만 받는다, A28) */
export const PHOTO_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export const PHOTO_SOURCE_MAX_BYTES = 10 * 1024 * 1024;
/** 서버 한도 (A28) */
export const PHOTO_MAX_BYTES = 2 * 1024 * 1024;
export const PHOTO_SIZE = 512;
const QUALITY = 0.85;

export function photoProblem(file: Pick<File, "type" | "size">): string | null {
  if (!(PHOTO_TYPES as readonly string[]).includes(file.type)) return "PNG·JPEG·WebP 사진만 올릴 수 있어요.";
  if (file.size > PHOTO_SOURCE_MAX_BYTES) return "10MB 이하 사진을 골라 주세요.";
  return null;
}

/** 가운데 정사각형 영역 (원본 좌표) */
export function centerSquare(width: number, height: number): { sx: number; sy: number; side: number } {
  const side = Math.min(width, height);
  return { sx: Math.floor((width - side) / 2), sy: Math.floor((height - side) / 2), side };
}

/**
 * 프로필 사진 최적화 (F56): 가운데를 정사각형으로 잘라 512×512 WebP로 바꾼다.
 * 원본이 512보다 작으면 그 크기 그대로 둔다
 */
export async function toProfilePhoto(file: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  try {
    const { sx, sy, side } = centerSquare(bitmap.width, bitmap.height);
    const size = Math.min(PHOTO_SIZE, side);
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("canvas");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(bitmap, sx, sy, side, side, 0, 0, size, size);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", QUALITY));
    if (!blob || blob.type !== "image/webp" || blob.size > PHOTO_MAX_BYTES) throw new Error("encode");
    return blob;
  } finally {
    bitmap.close();
  }
}
