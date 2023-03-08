// Hook that triggers when element enters or exits viewport
import { MutableRefObject, useEffect, useState } from "react";

export default function useOnScreen<T extends Element>(
  ref: MutableRefObject<T>,
  rootMargin = "0px"
): boolean {
  // State and setter for storing whether element is visible
  const [isIntersecting, setIntersecting] = useState<boolean>(false);
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        // Update our state when observer callback fires
        // rootBounds is null when we navigate away from the page of the element.
        // Dont update state if that's the case to avoid memory leak
        if (entry.rootBounds !== null) {
          setIntersecting(entry.isIntersecting);
        }
      },
      {
        rootMargin,
      }
    );
    if (ref.current) {
      observer.observe(ref.current);
    }
    return () => {
      if (ref.current) {
        // eslint-disable-next-line react-hooks/exhaustive-deps
        observer.unobserve(ref.current);
      }
    };
  }, [ref, rootMargin]);
  return isIntersecting;
}
