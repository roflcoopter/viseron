export type SubscribeEventMessage = {
  type: "subscribe_event";
  event: string;
  debounce?: number;
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

export type SubscribeTimespansMessage = {
  type: "subscribe_timespans";
  camera_identifiers: string[];
  date: string | null;
  debounce?: number;
};

export type ExportRecordingMessage = {
  type: "export_recording";
  camera_identifier: string;
  recording_id: number;
};
export type ExportSnapshotMessage = {
  type: "export_snapshot";
  event_type: string;
  camera_identifier: string;
  snapshot_id: number;
};
export type ExportTimespanMessage = {
  type: "export_timespan";
  camera_identifier: string;
  start: number;
  end: number;
};

export function auth(accessToken: string) {
  return {
    type: "auth",
    access_token: accessToken,
  };
}

export function subscribeEvent(event: string, debounce?: number) {
  const message: SubscribeEventMessage = {
    type: "subscribe_event",
    event,
  };

  if (debounce) {
    message.debounce = debounce;
  }

  return message;
}

export function unsubscribeEvent(subscription: number) {
  return {
    type: "unsubscribe_event",
    subscription,
  };
}

export function subscribeStates(entity_id?: string, entity_ids?: string[]) {
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

export function subscribeTimespans(
  camera_identifiers: string[],
  date: string | null,
  debounce?: number,
) {
  const message: SubscribeTimespansMessage = {
    type: "subscribe_timespans",
    camera_identifiers,
    date,
    debounce,
  };
  return message;
}

export function unsubscribeTimespans(subscription: number) {
  return {
    type: "unsubscribe_timespans",
    subscription,
  };
}

export function exportRecording(
  camera_identifier: string,
  recording_id: number,
) {
  return {
    type: "export_recording",
    camera_identifier,
    recording_id,
  } as ExportRecordingMessage;
}

export function exportSnapshot(
  event_type: string,
  camera_identifier: string,
  snapshot_id: number,
) {
  return {
    type: "export_snapshot",
    event_type,
    camera_identifier,
    snapshot_id,
  } as ExportSnapshotMessage;
}

export function exportTimespan(
  camera_identifier: string,
  start: number,
  end: number,
) {
  return {
    type: "export_timespan",
    camera_identifier,
    start,
    end,
  } as ExportTimespanMessage;
}

export function renderTemplate(template: string) {
  return {
    type: "render_template",
    template,
  };
}
