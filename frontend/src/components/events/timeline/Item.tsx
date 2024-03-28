import { memo } from "react";

import { ActivityLine } from "components/events/timeline/ActivityLine";
import { ObjectEvent } from "components/events/timeline/ObjectEvent";
import { TimeTick } from "components/events/timeline/TimeTick";
import { TimelineItem } from "components/events/timeline/utils";

export const itemEqual = (
  prevItem: Readonly<ItemProps>,
  nextItem: Readonly<ItemProps>,
) =>
  prevItem.item.time === nextItem.item.time &&
  prevItem.item.availableTimespan === nextItem.item.availableTimespan &&
  prevItem.item.activityLineVariant === nextItem.item.activityLineVariant &&
  prevItem.item.timedEvent?.start_timestamp ===
    nextItem.item.timedEvent?.start_timestamp &&
  prevItem.item.timedEvent?.end_timestamp ===
    nextItem.item.timedEvent?.end_timestamp &&
  prevItem.item.snapshotEvent?.timestamp ===
    nextItem.item.snapshotEvent?.timestamp;

type ItemProps = {
  item: TimelineItem;
};

export const Item = memo(
  ({ item }: ItemProps): JSX.Element => (
    <>
      <TimeTick key={`tick-${item.time}`} time={item.time} />
      <ActivityLine
        key={`line-${item.time}`}
        active={!!item.activityLineVariant}
        cameraEvent={item.timedEvent}
        variant={item.activityLineVariant}
        availableTimespan={!!item.availableTimespan}
      />
      {item.snapshotEvent ? (
        <ObjectEvent
          key={`object-${item.time}`}
          objectEvent={item.snapshotEvent}
        />
      ) : null}
    </>
  ),
  itemEqual,
);
