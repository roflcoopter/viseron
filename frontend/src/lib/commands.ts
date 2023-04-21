import * as messages from "lib/messages";
import * as types from "lib/types";

import { Connection } from "./websockets";

export const getCameras = async (
  connection: Connection
): Promise<types.Cameras> => {
  const response = await connection.sendMessagePromise(messages.getCameras());
  return response;
};

export const subscribeCameras = async (
  connection: Connection,
  cameraCallback: (camera: types.Camera) => void
) => {
  const storedCameraCallback = cameraCallback;
  const _cameraCallback = (message: types.EventCameraRegistered) => {
    storedCameraCallback(message.data);
  };
  const subscription = await connection.subscribeEvent(
    "domain/registered/camera",
    _cameraCallback,
    true
  );
  return subscription;
};

export const subscribeRecording = async (
  connection: Connection,
  recordingCallback: (recordingEvent: types.EventRecorderComplete) => void
) => {
  const storedRecordingCallback = recordingCallback;
  const _recordingCallback = (message: types.EventRecorderComplete) => {
    storedRecordingCallback(message);
  };
  const subscription = await connection.subscribeEvent(
    "*/recorder/complete",
    _recordingCallback,
    true
  );
  return subscription;
};

export const getConfig = async (connection: Connection): Promise<string> => {
  const response = await connection.sendMessagePromise(messages.getConfig());
  return response.config;
};

export const saveConfig = (
  connection: Connection,
  config: string
): Promise<
  | types.WebSocketResultResponse["result"]
  | types.WebSocketResultErrorResponse["error"]
> => connection.sendMessagePromise(messages.saveConfig(config));

export const restartViseron = async (connection: Connection): Promise<void> => {
  await connection.sendMessagePromise(messages.restartViseron());
};

export const getEntities = async (
  connection: Connection
): Promise<types.Entities> =>
  connection.sendMessagePromise(messages.getEntities());

export const subscribeStates = async (
  connection: Connection,
  stateCallback: (stateChangedEvent: types.StateChangedEvent) => void,
  entity_id?: string,
  entity_ids?: string[],
  resubscribe = true
) => {
  const storedStateCallback = stateCallback;
  const subscription = await connection.subscribeStates(
    storedStateCallback,
    entity_id,
    entity_ids,
    resubscribe
  );
  return subscription;
};

export const subscribeEvent = async <T = types.Event>(
  connection: Connection,
  event: string,
  eventCallback: (event: T) => void
) => {
  const subscription = await connection.subscribeEvent(
    event,
    eventCallback,
    true
  );
  return subscription;
};
