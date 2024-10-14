import Hls from "hls.js";
import { useCallback, useEffect, useRef } from "react";
import { useShallow } from "zustand/react/shallow";

import {
  LIVE_EDGE_DELAY,
  findClosestFragment,
  findFragmentByTimestamp,
  getSeekTarget,
  useHlsStore,
  useReferencePlayerStore,
} from "components/events/utils";
import { dateToTimestampMillis } from "lib/helpers";

const SYNC_INTERVAL = 500; // Sync every 500ms
const MAX_DRIFT = 0.5; // Maximum allowed drift in seconds

interface SyncManagerProps {
  children: React.ReactNode;
}

const SyncManager: React.FC<SyncManagerProps> = ({ children }) => {
  const { hlsRefs } = useHlsStore();
  const { setReferencePlayer, isPlaying, setIsPlaying, setIsLive, isMuted } =
    useReferencePlayerStore(
      useShallow((state) => ({
        setReferencePlayer: state.setReferencePlayer,
        isPlaying: state.isPlaying,
        setIsPlaying: state.setIsPlaying,
        setIsLive: state.setIsLive,
        isMuted: state.isMuted,
      })),
    );
  const syncIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastReferencePlayerDateRef = useRef<Date | null>(null);

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

  const syncPlayers = useCallback(() => {
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
      lastReferencePlayerDateRef.current = referencePlayer.current.playingDate;
      playersWithTime.forEach((player) => {
        if (player !== referencePlayer) {
          const timeDiff =
            (dateToTimestampMillis(referencePlayer.current.playingDate!) -
              dateToTimestampMillis(player.current.playingDate!)) /
            1000;

          if (Math.abs(timeDiff) > MAX_DRIFT) {
            if (player.current.media!.paused) {
              // Check if we can seek and play the paused player
              if (
                seekSafely(player.current, referencePlayer.current.playingDate!)
              ) {
                player.current.media!.play();
              }
            } else {
              seekSafely(player.current, referencePlayer.current.playingDate!);
            }
          }
        }
      });
    } else {
      setReferencePlayer(null);
    }

    // Check if all players are paused
    if (playersWithTime.every((player) => player.current.media!.paused)) {
      const lastReferenceDate = lastReferencePlayerDateRef.current;

      if (lastReferenceDate) {
        let playerToPlayIndex = -1;
        let smallestDifference = Infinity;
        const lastReferenceTime = dateToTimestampMillis(lastReferenceDate);

        playersWithTime.forEach((player, index) => {
          const fragments =
            player.current.levels[player.current.currentLevel].details
              ?.fragments;
          if (!fragments || fragments.length === 0) {
            return;
          }

          const closestFragment = findClosestFragment(
            fragments,
            lastReferenceTime,
          );
          if (!closestFragment || !closestFragment.programDateTime) {
            return;
          }

          const difference = Math.abs(
            lastReferenceTime - closestFragment.programDateTime,
          );
          if (difference < smallestDifference) {
            smallestDifference = difference;
            playerToPlayIndex = index;
          }
        });

        if (playerToPlayIndex !== -1) {
          const playerToPlay = playersWithTime[playerToPlayIndex];
          playerToPlay.current.media!.play();
        }
      }
    }
  }, [
    hlsRefs,
    isMuted,
    isPlaying,
    seekSafely,
    setIsLive,
    setIsPlaying,
    setReferencePlayer,
  ]);

  useEffect(() => {
    syncIntervalRef.current = setInterval(syncPlayers, SYNC_INTERVAL);

    hlsRefs.forEach((player) => {
      if (player.current) {
        player.current.on(Hls.Events.ERROR, (_event: any, _data: any) => {
          player.current!.media!.pause();
        });
      }
    });

    return () => {
      if (syncIntervalRef.current) {
        clearInterval(syncIntervalRef.current);
      }
    };
  }, [hlsRefs, syncPlayers]);

  return <>{children}</>;
};

export default SyncManager;
