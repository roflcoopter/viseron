import { useLayoutEffect, useRef } from "react";

const isBrowser = typeof window !== `undefined`;

type Coordinates = {
  x: number;
  y: number;
};

function getScrollPosition() {
  if (!isBrowser) return { x: 0, y: 0 };

  return { x: window.scrollX, y: window.scrollY };
}

export function useScrollPosition(
  effect: (prevPos: Coordinates, currPos: Coordinates) => void
) {
  const position = useRef(getScrollPosition());

  useLayoutEffect(() => {
    const handleScroll = () => {
      const currPos = getScrollPosition();
      effect(position.current, currPos);
      position.current = currPos;
    };

    window.addEventListener("scroll", handleScroll);

    return () => window.removeEventListener("scroll", handleScroll);
  });
}
