import { useVirtualizer } from "@tanstack/react-virtual";
import { type JSX, memo, useEffect, useReducer } from "react";

import { Row } from "components/events/timeline/Row";
import {
  TICK_HEIGHT,
  TimelineItems,
  calculateItemCount,
  calculateTimeFromIndex,
  getItem,
  useScrollingStore,
} from "components/events/utils";

type VirtualListProps = {
  parentRef: React.MutableRefObject<HTMLDivElement | null>;
  startRef: React.MutableRefObject<number>;
  endRef: React.MutableRefObject<number>;
  timelineItems: TimelineItems;
};

export const VirtualList = memo(
  ({
    parentRef,
    startRef,
    endRef,
    timelineItems,
  }: VirtualListProps): JSX.Element => {
    const rowVirtualizer = useVirtualizer({
      count: calculateItemCount(startRef, endRef),
      getScrollElement: () => parentRef!.current,
      estimateSize: () => TICK_HEIGHT,
      overscan: 10,
    });

    // In some cases, the parentRef is not attached during the first render,
    // causing the virtualizer to not find the scroll element.
    // The reducer forces a re-render to retry finding the scroll element.
    const [, retryScrollElement] = useReducer((count: number) => count + 1, 0);
    useEffect(() => {
      if (!rowVirtualizer.scrollElement && parentRef.current) {
        retryScrollElement();
      }
    });

    // Sync isScrolling with rowVirtualizer.isScrolling to avoid prop drilling
    const { setIsScrolling } = useScrollingStore();
    useEffect(() => {
      const next = rowVirtualizer.isScrolling;
      if (useScrollingStore.getState().isScrolling !== next) {
        setIsScrolling(next);
      }
    }, [rowVirtualizer.isScrolling, setIsScrolling]);

    return (
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          position: "relative",
          width: "100%",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualItem) => {
          const time = calculateTimeFromIndex(startRef, virtualItem.index);
          const item = getItem(time, timelineItems);
          return (
            <Row
              key={`item-${item.time}`}
              virtualItem={virtualItem}
              item={item}
            />
          );
        })}
      </div>
    );
  },
);
