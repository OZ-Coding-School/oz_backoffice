import { useQuery } from "@tanstack/react-query";
import { Download, FileText, Info } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

import {
  artifactLinkQuery,
  artifactsQuery,
  summaryMarkdownQuery,
  transcriptEntriesQuery,
  type Artifact,
  type MentoringSession,
} from "../api";
import {
  activeEntryIndex,
  entryOffset,
  formatClock,
  groupRecordings,
  missingRecordingState,
  recordingLabel,
  type Recording,
} from "../replay";
import { VideoPlayer, type VideoPlayerHandle } from "./video-player";

/** 다시 보기 (Figma `Column / 다시 보기 (FE-5b)`, F35·A68·A69·A71). 완료 세션만 */
export function ReplaySection({ session }: { session: MentoringSession }) {
  const artifacts = useQuery(artifactsQuery(session.id));
  const recordings = useMemo(() => groupRecordings(artifacts.data ?? []), [artifacts.data]);
  const [picked, setPicked] = useState(0);
  const recording = recordings[Math.min(picked, recordings.length - 1)];
  // 화면을 연 시각으로 정리 중·없음을 나눈다
  const [now] = useState(() => new Date());

  return (
    <section
      aria-labelledby="replay"
      className="flex flex-col gap-4 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
    >
      {artifacts.isPending ? (
        <>
          <h2 id="replay" className="text-h3 text-foreground">
            다시 보기
          </h2>
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        </>
      ) : artifacts.isError ? (
        <>
          <h2 id="replay" className="text-h3 text-foreground">
            다시 보기
          </h2>
          <ErrorState onRetry={() => void artifacts.refetch()} />
        </>
      ) : recording ? (
        <Viewer
          key={recording.key}
          session={session}
          recordings={recordings}
          recording={recording}
          picked={recordings.indexOf(recording)}
          onPick={setPicked}
        />
      ) : (
        <>
          <h2 id="replay" className="text-h3 text-foreground">
            다시 보기
          </h2>
          <MissingNotice state={missingRecordingState(session, now)} />
        </>
      )}
    </section>
  );
}

function MissingNotice({ state }: { state: "processing" | "none" }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg bg-muted px-5 py-5 text-center">
      <p className="text-body-strong text-foreground">
        {state === "processing" ? "녹화를 정리하고 있어요" : "이 세션은 녹화가 없어요"}
      </p>
      {state === "processing" ? (
        <p className="text-caption text-muted-foreground">
          세션이 끝나고 1시간 안에 영상·전사본·스마트 메모가 올라와요
        </p>
      ) : null}
    </div>
  );
}

function Viewer({
  session,
  recordings,
  recording,
  picked,
  onPick,
}: {
  session: MentoringSession;
  recordings: Recording[];
  recording: Recording;
  picked: number;
  onPick: (index: number) => void;
}) {
  const video = recording.video as Artifact; // groupRecordings가 영상이 있는 회의만 남긴다
  const link = useQuery(artifactLinkQuery(session.id, video.id));
  const player = useRef<VideoPlayerHandle>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState<number | null>(null);
  const ready = [recording.transcript && "전사본", recording.summary && "스마트 메모"].filter(Boolean).join("·");
  const meta = [duration ? `녹화 ${Math.round(duration / 60)}분` : null, ready ? `${ready} 정리됨` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <div className="flex items-center gap-3">
        <h2 id="replay" className="flex-1 text-h3 text-foreground">
          다시 보기
        </h2>
        {meta ? <span className="hidden text-caption text-muted-foreground md:inline">{meta}</span> : null}
        {link.data ? (
          <a
            href={link.data.download_url}
            download
            className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-label text-foreground outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download aria-hidden className="size-4" />
            내려받기
          </a>
        ) : null}
      </div>
      {recordings.length > 1 ? (
        <div role="radiogroup" aria-label="녹화 고르기" className="flex flex-wrap gap-2">
          {recordings.map((r, i) => (
            <button
              key={r.key}
              type="button"
              role="radio"
              aria-checked={i === picked}
              onClick={() => onPick(i)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-caption outline-none focus-visible:ring-2 focus-visible:ring-ring",
                i === picked
                  ? "border-primary bg-accent text-primary-text"
                  : "border-border bg-background text-foreground hover:bg-accent",
              )}
            >
              {recordingLabel(r, i)}
            </button>
          ))}
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_22.5rem] lg:gap-4">
        <div>
          {link.isError ? (
            <ErrorState onRetry={() => void link.refetch()} />
          ) : link.data ? (
            <VideoPlayer ref={player} src={link.data.url} onTime={setTime} onDuration={setDuration} />
          ) : (
            <div className="flex aspect-video items-center justify-center rounded-lg bg-black">
              <Spinner />
            </div>
          )}
        </div>
        {/* 데스크톱은 패널 높이를 영상에 맞춘다 */}
        <div className="lg:relative">
          <SidePanel session={session} recording={recording} time={time} onSeek={(s) => player.current?.seek(s)} />
        </div>
      </div>
    </>
  );
}

type Tab = "transcript" | "summary";

function SidePanel({
  session,
  recording,
  time,
  onSeek,
}: {
  session: MentoringSession;
  recording: Recording;
  time: number;
  onSeek: (seconds: number) => void;
}) {
  const [tab, setTab] = useState<Tab>("transcript");
  const doc = tab === "transcript" ? recording.transcript : recording.summary;
  const pdf = useQuery({ ...artifactLinkQuery(session.id, doc?.id ?? ""), enabled: !!doc });
  const tabs: { value: Tab; label: string }[] = [
    { value: "transcript", label: "전사본" },
    { value: "summary", label: "스마트 메모" },
  ];
  return (
    <div className="flex h-90 flex-col overflow-hidden rounded-lg border border-border bg-card lg:absolute lg:inset-0 lg:h-auto">
      <div role="tablist" aria-label="녹화 문서" className="flex gap-1 border-b border-border px-3">
        {tabs.map((t) => (
          <button
            key={t.value}
            type="button"
            role="tab"
            id={`replay-tab-${t.value}`}
            aria-selected={tab === t.value}
            aria-controls="replay-panel"
            onClick={() => setTab(t.value)}
            className={cn(
              "-mb-px h-10 border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
              tab === t.value
                ? "border-primary text-primary-text"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="replay-panel"
        aria-labelledby={`replay-tab-${tab}`}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-3"
      >
        {tab === "transcript" ? (
          recording.transcript ? (
            <Transcript
              session={session}
              artifact={recording.transcript}
              startedAt={recording.startedAt}
              time={time}
              onSeek={onSeek}
            />
          ) : (
            <Pending text="전사본을 정리하고 있어요" />
          )
        ) : recording.summary ? (
          <Summary session={session} artifact={recording.summary} />
        ) : (
          <Pending text="스마트 메모를 정리하고 있어요" />
        )}
      </div>
      <div className="flex items-center gap-2 border-t border-border px-3 py-2.5">
        <span className="flex-1 text-caption text-muted-foreground">
          {tab === "transcript" ? "전사본" : "스마트 메모"} · 자동 생성 문서
        </span>
        {pdf.data ? (
          <a
            href={pdf.data.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-label text-foreground outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
          >
            <FileText aria-hidden className="size-4" />
            PDF로 보기
          </a>
        ) : null}
      </div>
    </div>
  );
}

function Pending({ text }: { text: string }) {
  return <p className="py-6 text-center text-body-sm text-muted-foreground">{text}</p>;
}

function Transcript({
  session,
  artifact,
  startedAt,
  time,
  onSeek,
}: {
  session: MentoringSession;
  artifact: Artifact;
  startedAt: string | null;
  time: number;
  onSeek: (seconds: number) => void;
}) {
  const entries = useQuery(transcriptEntriesQuery(session.id, artifact.id));
  const offsets = useMemo(() => (entries.data ?? []).map((e) => entryOffset(e, startedAt)), [entries.data, startedAt]);
  const active = activeEntryIndex(offsets, time);
  const activeRef = useRef<HTMLButtonElement>(null);
  // 재생 중인 문장이 패널 밖으로 나가면 따라 내린다
  useEffect(() => {
    if (active < 0) return;
    activeRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [active]);

  if (entries.isPending) {
    return (
      <div className="flex justify-center py-6">
        <Spinner />
      </div>
    );
  }
  if (entries.isError) return <ErrorState onRetry={() => void entries.refetch()} />;
  if (entries.data.length === 0) return <Pending text="전사 문장을 정리하고 있어요" />;
  return (
    <div className="flex flex-col gap-2">
      {startedAt ? (
        <p className="inline-flex items-center gap-1.5 text-caption text-muted-foreground">
          <Info aria-hidden className="size-3" />
          문장을 누르면 그 시점으로 이동해요
        </p>
      ) : null}
      <ol className="flex flex-col gap-1">
        {entries.data.map((e, i) => {
          const offset = offsets[i] ?? null;
          const isActive = i === active;
          return (
            <li key={e.sequence}>
              <button
                ref={isActive ? activeRef : undefined}
                type="button"
                disabled={offset === null}
                aria-current={isActive ? "true" : undefined}
                onClick={() => offset !== null && onSeek(offset)}
                className={cn(
                  "flex w-full gap-3 rounded-md px-2 py-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default",
                  isActive ? "bg-accent" : "hover:bg-muted",
                )}
              >
                <span className="w-10 shrink-0 pt-0.5 font-mono text-caption text-muted-foreground">
                  {offset === null ? "" : formatClock(offset)}
                </span>
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-caption-strong text-foreground">{e.speaker_name}</span>
                  <span className="text-body-sm text-foreground">{e.text}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Summary({ session, artifact }: { session: MentoringSession; artifact: Artifact }) {
  const markdown = useQuery(summaryMarkdownQuery(session.id, artifact.id));
  if (markdown.isPending) {
    return (
      <div className="flex justify-center py-6">
        <Spinner />
      </div>
    );
  }
  if (markdown.isError) return <ErrorState onRetry={() => void markdown.refetch()} />;
  return <Markdown>{markdown.data.markdown}</Markdown>;
}
