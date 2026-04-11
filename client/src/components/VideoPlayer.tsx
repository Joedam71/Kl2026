import { useEffect, useRef, useState, useCallback } from 'react';
import { ArrowLeft, Play, Pause, SkipBack, SkipForward, Volume2, VolumeX, Maximize, Minimize } from 'lucide-react';
import { streamUrl, progressApi } from '../api/client';
import { useStore } from '../store/useStore';
import { mediaApi } from '../api/client';
import type { Media } from '../types';

function formatTime(s: number): string {
  if (!isFinite(s) || s < 0) return '0:00';
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

export default function VideoPlayer() {
  const { playingId, stopPlaying } = useStore();
  const [media, setMedia] = useState<Media | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);

  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load media info + saved progress
  useEffect(() => {
    if (!playingId) { setMedia(null); return; }

    mediaApi.getOne(playingId).then(setMedia).catch(() => {});
    progressApi.get(playingId).then(prog => {
      if (prog.position_seconds > 5 && videoRef.current) {
        videoRef.current.currentTime = prog.position_seconds;
      }
    }).catch(() => {});
  }, [playingId]);

  // Auto-play once video is ready
  const handleLoadedMetadata = () => {
    setDuration(videoRef.current?.duration ?? 0);
    videoRef.current?.play().catch(() => {});
  };

  // Track time updates
  const handleTimeUpdate = () => {
    const v = videoRef.current;
    if (!v) return;
    setCurrentTime(v.currentTime);
    if (v.buffered.length > 0) {
      setBuffered(v.buffered.end(v.buffered.length - 1));
    }
  };

  const handlePlayState = () => setPlaying(!(videoRef.current?.paused ?? true));

  // Save progress every 5s
  useEffect(() => {
    if (!playingId) return;
    saveTimer.current = setInterval(() => {
      const v = videoRef.current;
      if (!v || !v.duration) return;
      progressApi.save(playingId, v.currentTime, v.duration).catch(() => {});
    }, 5000);
    return () => { if (saveTimer.current) clearInterval(saveTimer.current); };
  }, [playingId]);

  // Auto-hide controls
  const showAndResetTimer = useCallback(() => {
    setShowControls(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => {
      if (!videoRef.current?.paused) setShowControls(false);
    }, 3000);
  }, []);

  useEffect(() => {
    showAndResetTimer();
    return () => { if (hideTimer.current) clearTimeout(hideTimer.current); };
  }, [showAndResetTimer]);

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const v = videoRef.current;
      if (!v) return;
      showAndResetTimer();
      switch (e.key) {
        case ' ': case 'k': e.preventDefault(); v.paused ? v.play() : v.pause(); break;
        case 'ArrowRight': e.preventDefault(); v.currentTime = Math.min(v.duration, v.currentTime + 10); break;
        case 'ArrowLeft':  e.preventDefault(); v.currentTime = Math.max(0, v.currentTime - 10); break;
        case 'ArrowUp':    e.preventDefault(); v.volume = Math.min(1, v.volume + 0.1); setVolume(v.volume); break;
        case 'ArrowDown':  e.preventDefault(); v.volume = Math.max(0, v.volume - 0.1); setVolume(v.volume); break;
        case 'm': v.muted = !v.muted; setMuted(v.muted); break;
        case 'f': toggleFullscreen(); break;
        case 'Escape': if (!fullscreen) handleExit(); break;
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showAndResetTimer, fullscreen]);

  // Fullscreen change listener
  useEffect(() => {
    const onFsChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  function togglePlayPause() {
    const v = videoRef.current;
    if (!v) return;
    v.paused ? v.play() : v.pause();
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const bar = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - bar.left) / bar.width;
    if (videoRef.current) videoRef.current.currentTime = pct * duration;
  }

  function handleVolumeChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = parseFloat(e.target.value);
    setVolume(v);
    if (videoRef.current) { videoRef.current.volume = v; videoRef.current.muted = v === 0; }
    setMuted(v === 0);
  }

  function toggleMute() {
    if (!videoRef.current) return;
    videoRef.current.muted = !videoRef.current.muted;
    setMuted(videoRef.current.muted);
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }

  function handleExit() {
    // Save final position
    const v = videoRef.current;
    if (v && playingId && v.duration) {
      progressApi.save(playingId, v.currentTime, v.duration).catch(() => {});
    }
    stopPlaying();
  }

  if (!playingId) return null;

  const seekPct = duration > 0 ? (currentTime / duration) * 100 : 0;
  const buffPct = duration > 0 ? (buffered / duration) * 100 : 0;

  return (
    <div
      ref={containerRef}
      className="player-page"
      onMouseMove={showAndResetTimer}
      onClick={togglePlayPause}
      style={{ cursor: showControls ? 'default' : 'none' }}
    >
      <video
        ref={videoRef}
        className="player-video"
        src={streamUrl(playingId)}
        onLoadedMetadata={handleLoadedMetadata}
        onTimeUpdate={handleTimeUpdate}
        onPlay={handlePlayState}
        onPause={handlePlayState}
        onEnded={() => { setPlaying(false); setShowControls(true); }}
        preload="auto"
      />

      <div
        className={`player-controls-overlay ${showControls ? 'visible' : ''}`}
        onClick={e => e.stopPropagation()}
      >
        {/* Top bar */}
        <div className="player-top">
          <button className="player-back-btn" onClick={handleExit}>
            <ArrowLeft size={20} /> Back
          </button>
          {media && <span className="player-title">{media.title}</span>}
        </div>

        {/* Center controls */}
        <div className="player-center">
          <button
            className="player-center-btn"
            onClick={() => { if (videoRef.current) videoRef.current.currentTime -= 10; }}
            title="Rewind 10s"
          >
            <SkipBack size={28} />
          </button>

          <button
            className="player-center-btn player-center-btn--play"
            onClick={togglePlayPause}
            title={playing ? 'Pause' : 'Play'}
          >
            {playing
              ? <Pause size={32} fill="currentColor" />
              : <Play size={32} fill="currentColor" />
            }
          </button>

          <button
            className="player-center-btn"
            onClick={() => { if (videoRef.current) videoRef.current.currentTime += 10; }}
            title="Forward 10s"
          >
            <SkipForward size={28} />
          </button>
        </div>

        {/* Bottom controls */}
        <div className="player-bottom">
          {/* Seek bar */}
          <div className="player-seekbar-wrap">
            <span className="player-time">{formatTime(currentTime)}</span>
            <div className="player-seekbar" onClick={seek}>
              <div className="player-seekbar-buffered" style={{ width: `${buffPct}%` }} />
              <div className="player-seekbar-progress" style={{ width: `${seekPct}%` }} />
              <div className="player-seekbar-thumb" style={{ left: `${seekPct}%` }} />
            </div>
            <span className="player-time" style={{ textAlign: 'right' }}>{formatTime(duration)}</span>
          </div>

          {/* Action row */}
          <div className="player-actions-row">
            <button
              className="player-action-btn"
              onClick={togglePlayPause}
              title={playing ? 'Pause (Space)' : 'Play (Space)'}
            >
              {playing ? <Pause size={22} /> : <Play size={22} />}
            </button>

            <div className="player-volume-wrap">
              <button className="player-action-btn" onClick={toggleMute} title="Mute (M)">
                {muted || volume === 0 ? <VolumeX size={20} /> : <Volume2 size={20} />}
              </button>
              <input
                type="range"
                min="0" max="1" step="0.05"
                value={muted ? 0 : volume}
                onChange={handleVolumeChange}
                className="player-volume-slider"
                onClick={e => e.stopPropagation()}
              />
            </div>

            <div className="player-spacer" />

            <button
              className="player-action-btn"
              onClick={toggleFullscreen}
              title="Fullscreen (F)"
            >
              {fullscreen ? <Minimize size={20} /> : <Maximize size={20} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
