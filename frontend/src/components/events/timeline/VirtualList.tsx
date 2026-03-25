import { useVirtualizer } from "@tanstack/react-virtual";
import { type JSX, memo, useEffect } from "react";

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
