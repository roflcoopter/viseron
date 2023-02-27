export type SubscribeEventMessage = {
  type: "subscribe_event";
  event: string;
};

export type SubscribeStatesMessage =
  | {
      type: "subscribe_states";
      entity_id?: string;
    }
  | {
      type: "subscribe_states";
      entity_ids?: string[];
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

export function subscribeStates(entity_id?: string, entity_ids?: string[]) {
  if (!entity_id && !entity_ids) {
    throw new Error("Must specify either entity_id or entity_ids");
  }
  if (entity_id && entity_ids) {
    throw new Error("Cannot specify both entity_id and entity_ids");
  }
  let message: SubscribeStatesMessage;
  if (entity_id) {
    message = {
      type: "subscribe_states",
      entity_id,
    };
  } else {
    message = {
      type: "subscribe_states",
      entity_ids,
    };
  }
  return message;
}

export function unsubscribeStates(subscription: number) {
  return {
    type: "unsubscribe_states",
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
