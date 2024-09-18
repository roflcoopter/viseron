import { useEffect } from "react";

export const useResizeObserver = (
  ref: React.MutableRefObject<HTMLDivElement | null>,
  callback: ResizeObserverCallback,
) => {
  useEffect(() => {
    let resizeObserver: ResizeObserver | null = null;
    if (ref.current) {
      resizeObserver = new ResizeObserver(callback);
      resizeObserver.observe(ref.current);
    }
    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, [callback, ref]);
};
