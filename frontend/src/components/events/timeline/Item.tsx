import { memo } from "react";

import { SnapshotEvent } from "components/events/SnapshotEvent";
import { ActivityLine } from "components/events/timeline/ActivityLine";
import { TimeTick } from "components/events/timeline/TimeTick";
import { TimelineItem } from "components/events/utils";

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
  prevItem.item.snapshotEvents?.length === nextItem.item.snapshotEvents?.length;

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
      {item.snapshotEvents ? (
        <SnapshotEvent
          key={`snapshot-${item.time}`}
          events={item.snapshotEvents}
        />
      ) : null}
    </>
  ),
  itemEqual,
);
