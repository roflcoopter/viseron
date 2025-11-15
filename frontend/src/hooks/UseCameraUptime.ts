import { useCallback, useEffect, useMemo, useReducer } from "react";

interface UptimeData {
  connectedSince: number | null;
  uptime: string;
  isConnected: boolean;
}

interface UptimeState {
  connectedSince: number | null;
  uptime: string;
}

type UptimeAction =
  | { type: "CONNECT"; timestamp: number }
  | { type: "DISCONNECT" }
  | { type: "UPDATE_UPTIME"; uptime: string }
  | { type: "RESTORE"; timestamp: number };

function uptimeReducer(state: UptimeState, action: UptimeAction): UptimeState {
  switch (action.type) {
    case "CONNECT":
    case "RESTORE":
      return {
        ...state,
        connectedSince: action.timestamp,
      };
    case "DISCONNECT":
      return {
        ...state,
        connectedSince: null,
        uptime: "--:--:--",
      };
    case "UPDATE_UPTIME":
      return {
        ...state,
        uptime: action.uptime,
      };
    default:
      return state;
  }
}

export function useCameraUptime(
  cameraIdentifier: string,
  isConnected: boolean,
): UptimeData {
  const storageKey = useMemo(
    () => `camera_uptime_${cameraIdentifier}`,
    [cameraIdentifier],
  );

  const [state, dispatch] = useReducer(uptimeReducer, {
    connectedSince: null,
    uptime: "--:--:--",
  });

  // Handle connection state changes
  useEffect(() => {
    if (isConnected) {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        dispatch({ type: "RESTORE", timestamp: parseInt(stored, 10) });
      } else {
        const now = Date.now();
        localStorage.setItem(storageKey, now.toString());
        dispatch({ type: "CONNECT", timestamp: now });
      }
    } else {
      localStorage.removeItem(storageKey);
      dispatch({ type: "DISCONNECT" });
    }
  }, [isConnected, storageKey]);

  // Format uptime display
  const formatUptime = useCallback((startTime: number): string => {
    const now = Date.now();
    const diff = now - startTime;

    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return `${days}d ${hours % 24}h ${minutes % 60}m`;
    }
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    }
    return `${seconds}s`;
  }, []);

  // Update uptime display every second when connected
  useEffect(() => {
    if (!state.connectedSince || !isConnected) {
      return undefined;
    }

    const updateUptime = () => {
      // Double check if still connected before updating
      if (!isConnected) {
        return;
      }
      dispatch({
        type: "UPDATE_UPTIME",
        uptime: formatUptime(state.connectedSince!),
      });
    };

    // Update immediately
    updateUptime();

    // Update every second
    const interval = setInterval(updateUptime, 1000);

    return () => clearInterval(interval);
  }, [state.connectedSince, isConnected, formatUptime]);

  // Reset uptime when disconnected
  const displayUptime = useMemo(() => {
    if (!state.connectedSince || !isConnected) {
      return "--:--:--";
    }
    return state.uptime;
  }, [state.connectedSince, isConnected, state.uptime]);

  return {
    connectedSince: state.connectedSince,
    uptime: displayUptime,
    isConnected,
  };
}
