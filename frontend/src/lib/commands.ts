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
  entity_id?: string
) => {
  const storedStateCallback = stateCallback;
  const _stateCallback = (message: types.StateChangedEvent) => {
    if (entity_id && message.data.entity_id !== entity_id) {
      return;
    }
    storedStateCallback(message);
  };
  const subscription = await connection.subscribeEvent(
    "state_changed",
    _stateCallback,
    true
  );
  return subscription;
};
