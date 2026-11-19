import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

/**
 * 1:1 신청 단계 값 (F30): 새로고침해도 남도록 sessionStorage에 둔다.
 * 다른 사용자·기수의 값이면 버린다(owner). 신청이 끝나면 비운다.
 */
export interface ApplyDraft {
  owner: string | null;
  /** 고른 종류 (F31). 바뀌면 멘토·일정을 비운다 */
  kind: "one" | "team" | null;
  mentorId: string | null;
  duration: number | null;
  desiredTimes: string[];
  topic: string;
  detail: string;
}

const EMPTY: ApplyDraft = {
  owner: null,
  kind: null,
  mentorId: null,
  duration: null,
  desiredTimes: [],
  topic: "",
  detail: "",
};

interface DraftStore extends ApplyDraft {
  /** 주인이 바뀌었으면 비우고 true */
  ensureOwner: (owner: string) => boolean;
  update: (patch: Partial<Omit<ApplyDraft, "owner">>) => void;
  /** 종류를 정한다. 다른 종류였으면 멘토·진행 시간·일정을 비운다 */
  chooseKind: (kind: "one" | "team") => void;
  reset: () => void;
}

export const MAX_DESIRED = 3;

export const useApplyDraft = create<DraftStore>()(
  persist(
    (set, get) => ({
      ...EMPTY,
      ensureOwner: (owner) => {
        if (get().owner === owner) return false;
        set({ ...EMPTY, owner });
        return true;
      },
      update: (patch) => set(patch),
      chooseKind: (kind) => {
        if (get().kind !== kind) set({ kind, mentorId: null, duration: null, desiredTimes: [] });
      },
      reset: () => set({ ...EMPTY, owner: get().owner }),
    }),
    {
      name: "oz:apply",
      storage: createJSONStorage(() => sessionStorage),
      partialize: ({ owner, kind, mentorId, duration, desiredTimes, topic, detail }) => ({
        owner,
        kind,
        mentorId,
        duration,
        desiredTimes,
        topic,
        detail,
      }),
    },
  ),
);
