export type SubscribeEventMessage = {
  type: "subscribe_event";
  event: string;
};

export function subscribeEvent(event: string) {
  const message: SubscribeEventMessage = {
    type: "subscribe_event",
    event,
  };

  return message;
}

export function unsubscribeEvent(subscription: number) {
  return {
    type: "unsubscribe_event",
    subscription,
  };
}

export function getCameras() {
  return {
    type: "get_cameras",
  };
}
