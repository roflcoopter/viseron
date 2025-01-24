import Hls from "hls.js";
import { useCallback, useEffect } from "react";
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
import useControlledInterval from "hooks/UseControlledInterval";
import { dateToTimestamp, dateToTimestampMillis, sleep } from "lib/helpers";

const SYNC_INTERVAL = 100; // Sync interval in milliseconds
const MAX_DRIFT = 0.5; // Maximum allowed drift in seconds

interface SyncManagerProps {
  children: React.ReactNode;
}

const SyncManager: React.FC<SyncManagerProps> = ({ children }) => {
  const { hlsRefs, setHlsRefsError } = useHlsStore(
    useShallow((state) => ({
      hlsRefs: state.hlsRefs,
      setHlsRefsError: state.setHlsRefsError,
    })),
  );
  const {
    setReferencePlayer,
    isPlaying,
    setIsPlaying,
    setIsLive,
    isMuted,
    requestedTimestamp,
    playingDateRef,
  } = useReferencePlayerStore(
    useShallow((state) => ({
      setReferencePlayer: state.setReferencePlayer,
      isPlaying: state.isPlaying,
      setIsPlaying: state.setIsPlaying,
      setIsLive: state.setIsLive,
      isMuted: state.isMuted,
      requestedTimestamp: state.requestedTimestamp,
      playingDateRef: state.playingDateRef,
    })),
  );
  const seekSafely = useCallback((player: Hls, referenceDate: Date) => {
    if (!player.levels || player.levels.length === 0) {
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

    const referenceTimestamp = dateToTimestampMillis(referenceDate);
    const targetFragment = findFragmentByTimestamp(
      fragments,
      referenceTimestamp,
    );
    if (!targetFragment) {
      return false;
    }
    const seekTarget = getSeekTarget(targetFragment, referenceTimestamp);

    const seekable = player.media!.seekable;
    if (seekable.length === 0) {
      return false;
    }

    for (let i = 0; i < seekable.length; i++) {
      if (seekTarget >= seekable.start(i) && seekTarget <= seekable.end(i)) {
        player.media!.currentTime = seekTarget;
        return true;
      }
    }

    return false;
  }, []);

  const syncPlayers = useCallback(async () => {
    if (requestedTimestamp === playingDateRef.current) {
      await sleep(1000);
    }

    const playersWithTime = hlsRefs.filter(
      (player): player is React.MutableRefObject<Hls> =>
        player.current !== null && player.current.playingDate !== null,
    );

    // Sync mute state
    playersWithTime.forEach((player) => {
      player.current.media!.muted = isMuted;
    });

    if (!isPlaying) {
      return;
    }

    // Find the player with the latest playing date, ignoring paused players
    const referencePlayer =
      playersWithTime.reduce<React.MutableRefObject<Hls> | null>(
        (prev, current) => {
          if (prev === null) {
            return !current.current.media!.paused ? current : null;
          }
          return !current.current.media!.paused &&
            current.current.playingDate! > prev.current.playingDate!
            ? current
            : prev;
        },
        null,
      );

    // Sync all players to the reference player
    if (referencePlayer) {
      setReferencePlayer(referencePlayer.current);
      setIsLive(referencePlayer.current.latency < LIVE_EDGE_DELAY * 1.5);
      setIsPlaying(true);
      playingDateRef.current = referencePlayer.current.playingDate
        ? dateToTimestamp(referencePlayer.current.playingDate)
        : requestedTimestamp;
      playersWithTime.forEach((player) => {
        if (player !== referencePlayer) {
          const timeDiff =
            (dateToTimestampMillis(referencePlayer.current.playingDate!) -
              dateToTimestampMillis(player.current.playingDate!)) /
            1000;

          if (Math.abs(timeDiff) > MAX_DRIFT) {
            const seeked = seekSafely(
              player.current,
              referencePlayer.current.playingDate!,
            );
            if (seeked) {
              player.current
                .media!.play()
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
          }
        }
      });
    } else {
      setReferencePlayer(null);
    }

    // Check if all players are paused
    if (playersWithTime.every((player) => player.current.media!.paused)) {
      const playingDateMillis = playingDateRef.current * 1000;

      let playerToPlayIndex = -1;
      let smallestDifference = Infinity;

      playersWithTime.forEach((player, index) => {
        const fragments =
          player.current.levels[player.current.currentLevel].details?.fragments;
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
          playerToPlay.current.levels[playerToPlay.current.currentLevel].details
            ?.fragments;
        if (!fragments || fragments.length === 0) {
          return;
        }
        const closestFragment = findClosestFragment(
          fragments,
          playingDateMillis,
        );
        if (closestFragment && closestFragment.programDateTime) {
          playerToPlay.current.media!.currentTime = closestFragment.start;
        }
        playerToPlay.current
          .media!.play()
          .then(() => {
            setHlsRefsError(playerToPlay, null);
          })
          .catch(() => {
            // Ignore play errors
          });
      }
    }
  }, [
    hlsRefs,
    isMuted,
    isPlaying,
    playingDateRef,
    requestedTimestamp,
    seekSafely,
    setHlsRefsError,
    setIsLive,
    setIsPlaying,
    setReferencePlayer,
  ]);

  useControlledInterval(syncPlayers, SYNC_INTERVAL);

  useEffect(() => {
    hlsRefs.forEach((player) => {
      if (player.current) {
        player.current.on(Hls.Events.ERROR, (_event, data) => {
          // Dont pause if this is the only playing player
          console.warn("SyncManager: Error event", data);
          if (
            hlsRefs.filter((p) => p.current && !p.current.media!.paused)
              .length === 1
          ) {
            player.current!.media!.play().catch(() => {
              // Ignore play errors
            });
            return;
          }

          if (data.details === Hls.ErrorDetails.BUFFER_NUDGE_ON_STALL) {
            player.current!.media!.play().catch(() => {
              // Ignore play errors
            });
            return;
          }

          player.current!.media!.pause();
        });
      }
    });

    return () => {
      hlsRefs.forEach((player) => {
        if (player.current) {
          player.current.off(Hls.Events.ERROR);
        }
      });
    };
  }, [hlsRefs]);

  return <>{children}</>;
};

export default SyncManager;
