import { Dayjs } from "dayjs";
import Hls, { ErrorData } from "hls.js";
import { useCallback, useEffect, useRef } from "react";
import { useShallow } from "zustand/react/shallow";

import {
  HlsErrorCodes,
  LIVE_EDGE_DELAY,
  findClosestFragment,
  findFragmentByTimestamp,
  getSeekTarget,
  translateErrorCode,
  useHlsStore,
  useReferencePlayerStore,
} from "components/events/utils";
import { seekMediaAndStartLoad } from "components/player/hlsplayer/utils";
import useControlledInterval from "hooks/UseControlledInterval";
import { getDayjsFromDate } from "lib/helpers/dates";

const SYNC_INTERVAL = 250;
const IGNORE_DRIFT = 0.35;
const RATE_NUDGE_DRIFT = 2;
const HARD_SEEK_DRIFT = 4;
const HARD_SEEK_COOLDOWN_MS = 3000;
const MAX_RATE_NUDGE = 0.05;

interface SyncManagerProps {
  children: React.ReactNode;
}

function SyncManager({ children }: SyncManagerProps) {
  const { hlsRefs, setHlsRefsError } = useHlsStore(
    useShallow((state) => ({
      hlsRefs: state.hlsRefs,
      setHlsRefsError: state.setHlsRefsError,
    })),
  );

  const {
    setReferencePlayer,
    isPlaying,
    setIsLive,
    isLive,
    isMuted,
    playbackSpeed,
    requestedTimestamp,
    playingDateRef,
    referencePlayer: currentReferencePlayer,
  } = useReferencePlayerStore(
    useShallow((state) => ({
      setReferencePlayer: state.setReferencePlayer,
      isPlaying: state.isPlaying,
      setIsLive: state.setIsLive,
      isLive: state.isLive,
      isMuted: state.isMuted,
      playbackSpeed: state.playbackSpeed,
      requestedTimestamp: state.requestedTimestamp,
      playingDateRef: state.playingDateRef,
      referencePlayer: state.referencePlayer,
    })),
  );
  const lastHardSeekRef = useRef(new WeakMap<Hls, number>());

  const seekSafely = useCallback((player: Hls, referenceDate: Dayjs) => {
    if (!player.levels || player.levels.length === 0 || !player.media) {
      return false;
    }

    const currentLevel = player.levels[player.currentLevel];
    if (!currentLevel || !currentLevel.details) {
      return false;
    }

    const fragments = currentLevel.details.fragments;
    if (!fragments || fragments.length === 0) {
      return false;
    }

    const referenceTimestampMillis = referenceDate.valueOf();
    const targetFragment = findFragmentByTimestamp(
      fragments,
      referenceTimestampMillis,
    );
    if (!targetFragment) {
      return false;
    }
    const seekTarget = getSeekTarget(targetFragment, referenceTimestampMillis);

    const seekable = player.media.seekable;
    if (seekable.length === 0) {
      return false;
    }

    for (let i = 0; i < seekable.length; i++) {
      if (seekTarget >= seekable.start(i) && seekTarget <= seekable.end(i)) {
        seekMediaAndStartLoad(player, player.media, seekTarget);
        return true;
      }
    }

    return false;
  }, []);

  const setDriftCorrectionRate = useCallback(
    (player: Hls, driftSeconds: number) => {
      if (!player.media) {
        return;
      }
      const nudge =
        Math.min(Math.abs(driftSeconds) / RATE_NUDGE_DRIFT, 1) * MAX_RATE_NUDGE;
      player.media.playbackRate =
        driftSeconds > 0 ? playbackSpeed + nudge : playbackSpeed - nudge;
    },
    [playbackSpeed],
  );

  const correctDrift = useCallback(
    (
      player: React.MutableRefObject<Hls>,
      referenceDate: Dayjs,
      driftSeconds: number,
    ) => {
      if (!player.current.media) {
        return;
      }

      const absDrift = Math.abs(driftSeconds);
      if (absDrift <= IGNORE_DRIFT) {
        player.current.media.playbackRate = playbackSpeed;
        return;
      }

      if (absDrift < HARD_SEEK_DRIFT) {
        setDriftCorrectionRate(player.current, driftSeconds);
        return;
      }

      const now = performance.now();
      const lastHardSeek = lastHardSeekRef.current.get(player.current) ?? 0;
      if (now - lastHardSeek < HARD_SEEK_COOLDOWN_MS) {
        setDriftCorrectionRate(player.current, driftSeconds);
        return;
      }

      const seeked = seekSafely(player.current, referenceDate);
      if (seeked) {
        lastHardSeekRef.current.set(player.current, now);
        player.current.media.playbackRate = playbackSpeed;
        player.current.media
          .play()
          .then(() => {
            setHlsRefsError(player, null);
          })
          .catch(() => {
            // Ignore play errors
          });
      } else {
        setHlsRefsError(
          player,
          translateErrorCode(HlsErrorCodes.TIMESPAN_MISSING),
        );
      }
    },
    [playbackSpeed, seekSafely, setDriftCorrectionRate, setHlsRefsError],
  );

  const syncPlayers = useCallback(async () => {
    const playersWithTime = hlsRefs.filter(
      (player): player is React.MutableRefObject<Hls> =>
        player.current !== null &&
        player.current.playingDate !== null &&
        player.current.media !== null,
    );

    // Sync mute state
    playersWithTime.forEach((player) => {
      if (player.current.media) {
        player.current.media.muted = isMuted;
      }
    });

    if (!isPlaying) {
      return;
    }

    if (playersWithTime.length === 1) {
      const player = playersWithTime[0];
      if (currentReferencePlayer !== player.current) {
        setReferencePlayer(player.current);
      }

      const nextIsLive = player.current.latency < LIVE_EDGE_DELAY * 1.5;
      if (isLive !== nextIsLive) {
        setIsLive(nextIsLive);
      }

      playingDateRef.current = player.current.playingDate
        ? getDayjsFromDate(player.current.playingDate).unix()
        : requestedTimestamp;

      if (
        player.current.media &&
        player.current.media.playbackRate !== playbackSpeed
      ) {
        player.current.media.playbackRate = playbackSpeed;
      }
      return;
    }

    // Find the player with the latest playing date, ignoring paused players
    const referencePlayer =
      playersWithTime.reduce<React.MutableRefObject<Hls> | null>(
        (prev, current) => {
          if (prev === null) {
            return !current.current.media?.paused ? current : null;
          }
          return !current.current.media?.paused &&
            current.current.playingDate! > prev.current.playingDate!
            ? current
            : prev;
        },
        null,
      );

    // Sync all players to the reference player
    if (referencePlayer) {
      if (currentReferencePlayer !== referencePlayer.current) {
        setReferencePlayer(referencePlayer.current);
      }
      const nextIsLive =
        referencePlayer.current.latency < LIVE_EDGE_DELAY * 1.5;
      if (isLive !== nextIsLive) {
        setIsLive(nextIsLive);
      }
      playingDateRef.current = referencePlayer.current.playingDate
        ? getDayjsFromDate(referencePlayer.current.playingDate).unix()
        : requestedTimestamp;
      playersWithTime.forEach((player) => {
        if (player.current.media) {
          player.current.media.playbackRate = playbackSpeed;
        }
        if (player !== referencePlayer) {
          const referenceDate = getDayjsFromDate(
            referencePlayer.current.playingDate!,
          );
          const timeDiff =
            (referenceDate.valueOf() -
              getDayjsFromDate(player.current.playingDate!).valueOf()) /
            1000;

          correctDrift(player, referenceDate, timeDiff);
        }
      });
    } else {
      setReferencePlayer(null);
    }

    // If there are no players with time, play the first player
    if (playersWithTime.length === 0) {
      if (
        hlsRefs.length > 0 &&
        hlsRefs[0].current &&
        hlsRefs[0].current.media
      ) {
        hlsRefs[0].current.media
          .play()
          .then(() => {
            setHlsRefsError(hlsRefs[0], null);
          })
          .catch(() => {
            // Ignore play errors
          });
      }
    }

    // Check if all players are paused
    if (
      playersWithTime.every((player) => player.current.media?.paused ?? true)
    ) {
      const playingDateMillis = playingDateRef.current * 1000;

      let playerToPlayIndex = -1;
      let smallestDifference = Infinity;

      playersWithTime.forEach((player, index) => {
        const fragments =
          player.current.levels[player.current.currentLevel]?.details
            ?.fragments;
        if (!fragments || fragments.length === 0) {
          return;
        }

        const closestFragment = findClosestFragment(
          fragments,
          playingDateMillis,
        );
        if (!closestFragment || !closestFragment.programDateTime) {
          return;
        }

        const difference = Math.abs(
          playingDateMillis - closestFragment.programDateTime,
        );
        if (difference < smallestDifference) {
          smallestDifference = difference;
          playerToPlayIndex = index;
        }
      });

      if (playerToPlayIndex !== -1) {
        const playerToPlay = playersWithTime[playerToPlayIndex];
        const fragments =
          playerToPlay.current.levels[playerToPlay.current.currentLevel]
            ?.details?.fragments;
        if (!fragments || fragments.length === 0) {
          return;
        }
        const closestFragment = findClosestFragment(
          fragments,
          playingDateMillis,
        );
        if (
          closestFragment &&
          closestFragment.programDateTime &&
          playerToPlay.current.media
        ) {
          seekMediaAndStartLoad(
            playerToPlay.current,
            playerToPlay.current.media,
            closestFragment.start,
          );
        }
        if (playerToPlay.current.media) {
          playerToPlay.current.media
            .play()
            .then(() => {
              setHlsRefsError(playerToPlay, null);
            })
            .catch(() => {
              // Ignore play errors
            });
        }
      }
    }
  }, [
    hlsRefs,
    correctDrift,
    currentReferencePlayer,
    isLive,
    isMuted,
    isPlaying,
    playbackSpeed,
    playingDateRef,
    requestedTimestamp,
    setHlsRefsError,
    setIsLive,
    setReferencePlayer,
  ]);

  useControlledInterval(syncPlayers, SYNC_INTERVAL, true);

  useEffect(() => {
    const errorHandlers = new Map<
      React.MutableRefObject<Hls | null>,
      (event: string, data: ErrorData) => void
    >();

    hlsRefs.forEach((player) => {
      if (player.current) {
        const handleError = (_event: string, data: ErrorData) => {
          // Dont pause if this is the only playing player
          // console.warn("SyncManager: Error event", data);
          if (
            hlsRefs.filter(
              (p) => p.current && p.current.media && !p.current.media.paused,
            ).length === 1
          ) {
            if (player.current!.media) {
              player.current!.media.play().catch(() => {
                // Ignore play errors
              });
            }
            return;
          }

          if (
            data.details === Hls.ErrorDetails.BUFFER_NUDGE_ON_STALL ||
            data.details === Hls.ErrorDetails.BUFFER_STALLED_ERROR ||
            data.details === Hls.ErrorDetails.LEVEL_LOAD_ERROR ||
            data.details === Hls.ErrorDetails.LEVEL_PARSING_ERROR
          ) {
            if (player.current!.media) {
              player.current!.media.play().catch(() => {
                // Ignore play errors
              });
            }
            return;
          }

          if (player.current!.media) {
            player.current!.media.pause();
          }
        };
        errorHandlers.set(player, handleError);
        player.current.on(Hls.Events.ERROR, handleError);
      }
    });

    return () => {
      hlsRefs.forEach((player) => {
        const handleError = errorHandlers.get(player);
        if (player.current && handleError) {
          player.current.off(Hls.Events.ERROR, handleError);
        }
      });
    };
  }, [hlsRefs]);

  return children;
}

export default SyncManager;
