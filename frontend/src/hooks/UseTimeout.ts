import { useCallback, useEffect, useMemo, useRef } from "react";

// A single pending timeout that is replaced by each start and cleared on unmount
export function useTimeout() {
  const timeoutRef = useRef<number | undefined>(undefined);

  const clear = useCallback(() => window.clearTimeout(timeoutRef.current), []);

  const start = useCallback(
    (callback: () => void, delay: number) => {
      clear();
      timeoutRef.current = window.setTimeout(callback, delay);
    },
    [clear],
  );

  useEffect(() => clear, [clear]);

  return useMemo(() => ({ start, clear }), [start, clear]);
}
