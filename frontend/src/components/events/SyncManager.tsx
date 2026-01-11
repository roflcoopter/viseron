import { Dayjs } from "dayjs";
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
import { sleep } from "lib/helpers";
import { getDayjsFromDate } from "lib/helpers/dates";

const SYNC_INTERVAL = 100; // Sync interval in milliseconds
const MAX_DRIFT = 0.5; // Maximum allowed drift in seconds

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
        player.media.currentTime = seekTarget;
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
      setReferencePlayer(referencePlayer.current);
      setIsLive(referencePlayer.current.latency < LIVE_EDGE_DELAY * 1.5);
      setIsPlaying(true);
      playingDateRef.current = referencePlayer.current.playingDate
        ? getDayjsFromDate(referencePlayer.current.playingDate).unix()
        : requestedTimestamp;
      playersWithTime.forEach((player) => {
        if (player !== referencePlayer) {
          const timeDiff =
            (getDayjsFromDate(referencePlayer.current.playingDate!).valueOf() -
              getDayjsFromDate(player.current.playingDate!).valueOf()) /
            1000;

          if (Math.abs(timeDiff) > MAX_DRIFT) {
            const seeked = seekSafely(
              player.current,
              getDayjsFromDate(referencePlayer.current.playingDate!),
            );
            if (seeked && player.current.media) {
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
          }
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
          playerToPlay.current.media.currentTime = closestFragment.start;
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

  useControlledInterval(syncPlayers, SYNC_INTERVAL, true);

  useEffect(() => {
    hlsRefs.forEach((player) => {
      if (player.current) {
        player.current.on(Hls.Events.ERROR, (_event, data) => {
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

  return children;
}

export default SyncManager;
