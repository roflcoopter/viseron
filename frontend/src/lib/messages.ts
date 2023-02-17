export type SubscribeEventMessage = {
  type: "subscribe_event";
  event: string;
};

export type SaveConfigMessage = {
  type: "save_config";
  config: string;
};

export function auth(accessToken: string) {
  return {
    type: "auth",
    access_token: accessToken,
  };
}

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

export function getConfig() {
  return {
    type: "get_config",
  };
}

export function saveConfig(config: string) {
  const message: SaveConfigMessage = {
    type: "save_config",
    config,
  };

  return message;
}

export function restartViseron() {
  return {
    type: "restart_viseron",
  };
}

export function ping() {
  return {
    type: "ping",
  };
}

export function getEntities() {
  return {
    type: "get_entities",
  };
}

