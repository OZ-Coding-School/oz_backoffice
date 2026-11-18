export interface BrandCopy {
  headline: string;
  features?: string[];
}

/** 수강생·멘토 화면 소개 문구 (F22). 운영진 화면은 FE-1c에서 기능 목록과 함께 쓴다. */
export const MEMBER_BRAND: BrandCopy = { headline: "수강부터 수료까지\n필요한 지원을 한곳에서" };
