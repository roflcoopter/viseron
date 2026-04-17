import { useContext, useEffect } from "react";

import { ViseronContext } from "context/ViseronContext";
import { subscribeTimespans } from "lib/commands";
import * as types from "lib/types";
import { SubscriptionUnsubscribe } from "lib/websockets";

export const useSubscribeTimespans = (
  camera_identifiers: string[],
  date: string | null,
  timespanCallback: (message: types.HlsAvailableTimespans) => void,
  enabled = true,
  debounce?: number,
) => {
  const viseron = useContext(ViseronContext);

  useEffect(() => {
    if (!enabled) {
      return () => {};
    }

    let unmounted = false;
    let unsub: SubscriptionUnsubscribe | null = null;
    const subscribe = async () => {
      if (viseron.connection) {
        unsub = await subscribeTimespans(
          viseron.connection,
          camera_identifiers,
          date,
          timespanCallback,
          debounce,
        );
        if (unmounted) {
          unsub();
          unsub = null;
        }
      }
    };
    subscribe();

    return () => {
      unmounted = true;
      const unsubscribe = async () => {
        if (unsub) {
          try {
            await unsub();
          } catch (error) {
            // Connection is probably closed
          }
          unsub = null;
        }
      };
      unsubscribe();
    };
  }, [
    camera_identifiers,
    date,
    enabled,
    debounce,
    timespanCallback,
    viseron.connected,
    viseron.connection,
  ]);
};
