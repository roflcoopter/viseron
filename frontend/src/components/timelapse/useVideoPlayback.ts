import { RefObject, useEffect, useRef, useState } from "react";

type VideoPlaybackCallbacks = {
  // Called with the video's currentTime as it changes
  onTimeUpdate: (time: number) => void;
  // Called once the video shows a frame after playing or seeking
  onFrameShown: () => void;
};

/**
 * Track whether the video is playing or buffering. While playing, the
 * position is reported every animation frame.
 */
export function useVideoPlayback(
  videoRef: RefObject<HTMLVideoElement | null>,
  callbacks: VideoPlaybackCallbacks,
) {
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) {
      return () => {};
    }
    let animationFrame = 0;
    const updateTime = () =>
      callbacksRef.current.onTimeUpdate(video.currentTime);
    // timeupdate only fires a few times per second, too slow for the slider
    const tick = () => {
      updateTime();
      animationFrame = requestAnimationFrame(tick);
    };
    const onPlay = () => {
      setPlaying(true);
      cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(tick);
    };
    const onPause = () => {
      setPlaying(false);
      cancelAnimationFrame(animationFrame);
      updateTime();
    };
    const onWaiting = () => setBuffering(true);
    const onReady = () => setBuffering(false);
    const onFrameShown = () => {
      setBuffering(false);
      callbacksRef.current.onFrameShown();
    };
    const listeners: [string, () => void][] = [
      ["play", onPlay],
      ["pause", onPause],
      ["timeupdate", updateTime],
      ["waiting", onWaiting],
      ["seeking", onWaiting],
      ["canplay", onReady],
      ["playing", onFrameShown],
      ["seeked", onFrameShown],
    ];
    listeners.forEach(([event, listener]) =>
      video.addEventListener(event, listener),
    );
    return () => {
      cancelAnimationFrame(animationFrame);
      listeners.forEach(([event, listener]) =>
        video.removeEventListener(event, listener),
      );
    };
  }, [videoRef]);

  return { playing, buffering };
}

export function usePlaybackRate(
  videoRef: RefObject<HTMLVideoElement | null>,
  rate: number,
) {
  useEffect(() => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    // Loading a source resets playbackRate to defaultPlaybackRate
    video.defaultPlaybackRate = rate;
    video.playbackRate = rate;
  }, [videoRef, rate]);
}
