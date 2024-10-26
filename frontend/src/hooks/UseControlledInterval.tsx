import { useEffect, useRef } from "react";

// Hook where the interval only starts after the current execution is complete.
const useControlledInterval = (
  callback: () => Promise<void> | void,
  delay: number,
) => {
  const savedCallback = useRef<typeof callback>();
  const timeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the interval
  useEffect(() => {
    let isDestroyed = false;

    const tick = async () => {
      if (isDestroyed) return;

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

    // Start the first execution
    tick();

    return () => {
      isDestroyed = true;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [delay]);

  // Return method to manually clear the timeout
  return () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  };
};

export default useControlledInterval;
