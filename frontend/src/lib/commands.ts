import * as messages from "lib/messages";
import * as types from "lib/types";
import { Connection } from "./websockets";


export const getCameras = (async (connection: Connection): Promise<types.Cameras> => {
  const response = await connection.sendMessagePromise(messages.getCameras());
  const json = await JSON.parse(response);
  return json;
})

export const subscribeCameras = (async (connection: Connection, cameraCallback: (camera: types.Camera) => void) => {
  const storedCameraCallback = cameraCallback;
  const _cameraCallback = (message: types.CameraRegisteredEvent) => {
    storedCameraCallback(message.data);
  };
  const subscription = await connection.subscribeEvent(
    "domain/registered/camera",
    _cameraCallback,
    true
  );
  return subscription;
})

export const getConfig = (async (connection: Connection): Promise<string> => {
  const response = await connection.sendMessagePromise(messages.getConfig());
  return response.config;
})

export const saveConfig = (
  connection: Connection, 
  config: string
): Promise<
  types.WebSocketResultResponse["result"] | types.WebSocketResultErrorResponse["error"]
> => connection.sendMessagePromise(messages.saveConfig(config))

export const restartViseron = (async (connection: Connection): Promise<void> => {
  await connection.sendMessagePromise(messages.restartViseron());
})
