import { VirtualItem } from "@tanstack/react-virtual";
import { memo, useState } from "react";

import { Item, itemEqual } from "components/events/timeline/Item";
import { TimelineItem } from "components/events/timeline/utils";

const rowEqual = (prevItem: Readonly<RowProps>, nextItem: Readonly<RowProps>) =>
  prevItem.virtualItem === nextItem.virtualItem &&
  itemEqual({ item: prevItem.item }, { item: nextItem.item });

type RowProps = {
  virtualItem: VirtualItem;
  item: TimelineItem;
};

export const Row = memo(({ virtualItem, item }: RowProps): JSX.Element => {
  const [hover, setHover] = useState(false);

  return (
    <div
      key={item.time}
      onMouseEnter={() => {
        if (!item.snapshotEvent) {
          return;
        }
        setHover(true);
      }}
      onMouseLeave={() => {
        if (!item.snapshotEvent) {
          return;
        }
        setHover(false);
      }}
      style={{
        display: "flex",
        justifyContent: "start",
        position: "absolute",
        top: 0,
        left: 0,
        height: `${virtualItem.size}px`,
        width: "100%",
        transform: `translateY(${virtualItem.start}px)`,
        transition: "transform 0.2s linear",
        zIndex:
          item.snapshotEvent && hover ? 999 : item.snapshotEvent ? 998 : 1,
      }}
    >
      <Item item={item} />
    </div>
  );
}, rowEqual);
