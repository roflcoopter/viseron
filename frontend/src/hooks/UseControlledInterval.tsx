import { useEffect, useRef } from "react";
import { usePageVisibility } from "react-page-visibility";

// Hook where the interval only starts after the current execution is complete.
const useControlledInterval = (
  callback: () => Promise<void> | void,
  delay: number,
  pauseInvisible = false, // Pause the interval when the tab is not visible
) => {
  const savedCallback = useRef<typeof callback>(undefined);
  const timeoutRef = useRef<NodeJS.Timeout>(undefined);
  const isVisible = usePageVisibility();

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the interval
  useEffect(() => {
    let isDestroyed = false;

    const tick = async () => {
      if (isDestroyed) return;

      // Don't execute if we should pause when invisible and page is not visible
      if (pauseInvisible && !isVisible) return;

      try {
        // Execute the callback
        await savedCallback.current?.();
      } catch (error) {
        console.error("Error in interval callback:", error);
      }

      if (!isDestroyed) {
        // Schedule next execution only after the current one is complete
        timeoutRef.current = setTimeout(tick, delay);
      }
    };

    // Only start the interval if we're visible or pauseInvisible is false
    if (!pauseInvisible || isVisible) {
      tick();
    }

    return () => {
      isDestroyed = true;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [delay, pauseInvisible, isVisible]);

  // Return method to manually clear the timeout
  return () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  };
};

export default useControlledInterval;
