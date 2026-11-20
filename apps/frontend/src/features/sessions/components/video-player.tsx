import { Check, Maximize, Pause, Play, Video, Volume2, VolumeX } from "lucide-react";
import { useImperativeHandle, useRef, useState, type KeyboardEvent, type Ref } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

import { formatClock } from "../replay";

export interface VideoPlayerHandle {
  /** 그 위치(초)로 옮기고 재생한다 (전사 문장 클릭) */
  seek: (seconds: number) => void;
}

const RATES = [1, 1.25, 1.5, 2] as const;
const STEP_SECONDS = 5;

/**
 * 녹화 플레이어 (F35: 직접 만든 컨트롤).
 * 재생·일시정지(가운데 버튼·화면 클릭·스페이스), 현재/전체 시각, 진행 막대(←/→ 5초),
 * 재생 속도, 소리, 전체 화면.
 */
export function VideoPlayer({
  src,
  ref,
  onTime,
  onDuration,
}: {
  src: string;
  ref?: Ref<VideoPlayerHandle>;
  onTime?: (seconds: number) => void;
  onDuration?: (seconds: number) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [rate, setRate] = useState<number>(1);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(1);

  const seekTo = (seconds: number) => {
    const el = video.current;
    if (!el) return;
    const max = Number.isFinite(el.duration) ? el.duration : seconds;
    el.currentTime = Math.min(Math.max(0, seconds), max);
    setCurrent(el.currentTime);
    onTime?.(el.currentTime);
  };

  useImperativeHandle(ref, () => ({
    seek: (seconds) => {
      seekTo(seconds);
      void video.current?.play()?.catch(() => undefined);
    },
  }));

  const toggle = () => {
    const el = video.current;
    if (!el) return;
    if (el.paused) void el.play()?.catch(() => undefined);
    else el.pause();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    // 버튼·메뉴에서는 그 요소의 기본 동작을 쓴다. 진행 막대는 스스로 5초씩 움직인다
    if (target.closest("button, [role=menu], input")) return;
    if (e.key === " ") {
      e.preventDefault();
      toggle();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      seekTo(current + (e.key === "ArrowLeft" ? -STEP_SECONDS : STEP_SECONDS));
    }
  };

  const changeRate = (value: number) => {
    setRate(value);
    if (video.current) video.current.playbackRate = value;
  };

  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    if (video.current) video.current.muted = next;
  };

  const changeVolume = (value: number) => {
    setVolume(value);
    setMuted(value === 0);
    if (video.current) {
      video.current.volume = value;
      video.current.muted = value === 0;
    }
  };

  const fullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void box.current?.requestFullscreen?.();
  };

  return (
    <div
      ref={box}
      role="group"
      aria-label="녹화 플레이어"
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="flex flex-col overflow-hidden rounded-lg bg-black outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="relative aspect-video w-full">
        {/* 녹화에는 자막 파일이 없다. 전사본은 옆 패널에서 본다 */}
        {/* oxlint-disable-next-line jsx-a11y/media-has-caption */}
        <video
          ref={video}
          src={src}
          preload="metadata"
          playsInline
          className="size-full"
          onClick={toggle}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onLoadedMetadata={(e) => {
            setDuration(e.currentTarget.duration);
            onDuration?.(e.currentTarget.duration);
          }}
          onTimeUpdate={(e) => {
            setCurrent(e.currentTarget.currentTime);
            onTime?.(e.currentTarget.currentTime);
          }}
        />
        {playing ? null : (
          <button
            type="button"
            aria-label="재생"
            onClick={toggle}
            className="absolute top-1/2 left-1/2 flex size-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white/20 text-white outline-none hover:bg-white/30 focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Video aria-hidden className="size-7" />
          </button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 bg-black/90 px-3 py-2 text-white md:flex-nowrap">
        <ControlButton label={playing ? "일시정지" : "재생"} onClick={toggle}>
          {playing ? <Pause aria-hidden /> : <Play aria-hidden />}
        </ControlButton>
        <span className="mr-auto shrink-0 font-mono text-caption md:mr-0">
          {formatClock(current)} / {formatClock(duration)}
        </span>
        <input
          type="range"
          aria-label="재생 위치"
          min={0}
          max={duration || 0}
          step={STEP_SECONDS}
          value={Math.min(current, duration || 0)}
          aria-valuetext={formatClock(current)}
          onChange={(e) => seekTo(Number(e.currentTarget.value))}
          className="order-first h-1 min-w-0 basis-full cursor-pointer accent-primary md:order-none md:flex-1 md:basis-auto"
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={`재생 속도 ${rate}배`}
              className="shrink-0 rounded px-1 font-mono text-caption outline-none hover:bg-white/15 focus-visible:ring-2 focus-visible:ring-ring"
            >
              {rate}×
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {RATES.map((r) => (
              <DropdownMenuItem key={r} onSelect={() => changeRate(r)}>
                <Check aria-hidden className={cn("size-4", r === rate ? "opacity-100" : "opacity-0")} />
                {r}×
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <ControlButton label={muted ? "소리 켜기" : "소리 끄기"} onClick={toggleMute}>
          {muted ? <VolumeX aria-hidden /> : <Volume2 aria-hidden />}
        </ControlButton>
        <input
          type="range"
          aria-label="소리 크기"
          min={0}
          max={1}
          step={0.1}
          value={muted ? 0 : volume}
          onChange={(e) => changeVolume(Number(e.currentTarget.value))}
          className="hidden h-1 w-20 cursor-pointer accent-primary md:block"
        />
        <ControlButton label="전체 화면" onClick={fullscreen}>
          <Maximize aria-hidden />
        </ControlButton>
      </div>
    </div>
  );
}

function ControlButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      aria-label={label}
      onClick={onClick}
      className="size-8 shrink-0 px-0 text-white hover:bg-white/15 hover:text-white"
    >
      {children}
    </Button>
  );
}
