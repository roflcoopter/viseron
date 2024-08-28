import { MutableRefObject, createRef, useEffect } from "react";

const mountCount: MutableRefObject<number | null> = createRef();
mountCount.current = 0;

// This hook hides the scrollbar on the body element by adding a class
// that is defined in index.css
export const useHideScrollbar = () => {
  useEffect(() => {
    if (mountCount.current === null) {
      mountCount.current = 0;
    }
    mountCount.current += 1;
    document.body.classList.add("overflow-hidden");
    return () => {
      if (mountCount.current === null) {
        document.body.classList.remove("overflow-hidden");
        return;
      }
      mountCount.current -= 1;
      if (mountCount.current === 0) {
        document.body.classList.remove("overflow-hidden");
      }
    };
  }, []);
};
