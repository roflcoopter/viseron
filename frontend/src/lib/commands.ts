import { useContext, useEffect } from "react";

import { ViseronContext } from "context/ViseronContext";
import * as messages from "lib/messages";
import * as types from "lib/types";
import { Connection, SubscriptionUnsubscribe } from "lib/websockets";

export const getCameras = async (
  connection: Connection,
): Promise<types.Cameras> => {
  const response = await connection.sendMessagePromise(messages.getCameras());
  return response;
};

export const subscribeCameras = async (
  connection: Connection,
  cameraCallback: (camera: types.Camera) => void,
) => {
  const storedCameraCallback = cameraCallback;
  const _cameraCallback = (message: types.EventCameraRegistered) => {
    storedCameraCallback(message.data);
  };
  const subscription = await connection.subscribeEvent(
    "domain/registered/camera",
    _cameraCallback,
    true,
  );
  return subscription;
};

export const subscribeRecordingStart = async (
  connection: Connection,
  recordingCallback: (recordingEvent: types.EventRecorderStart) => void,
  camera_identifier = "*",
) => {
  const storedRecordingCallback = recordingCallback;
  const _recordingCallback = (message: types.EventRecorderStart) => {
    storedRecordingCallback(message);
  };
  const subscription = await connection.subscribeEvent(
    `${camera_identifier}/recorder/start`,
    _recordingCallback,
    true,
  );
  return subscription;
};

export const subscribeRecordingStop = async (
  connection: Connection,
  recordingCallback: (recordingEvent: types.EventRecorderStop) => void,
  camera_identifier = "*",
) => {
  const storedRecordingCallback = recordingCallback;
  const _recordingCallback = (message: types.EventRecorderStop) => {
    storedRecordingCallback(message);
  };
  const subscription = await connection.subscribeEvent(
    `${camera_identifier}/recorder/stop`,
    _recordingCallback,
    true,
  );
  return subscription;
};

export const getConfig = async (connection: Connection): Promise<string> => {
  const response = await connection.sendMessagePromise(messages.getConfig());
  return response.config;
};

export const saveConfig = (
  connection: Connection,
  config: string,
): Promise<
  | types.WebSocketResultResponse["result"]
  | types.WebSocketResultErrorResponse["error"]
> => connection.sendMessagePromise(messages.saveConfig(config));

export const restartViseron = async (connection: Connection): Promise<void> => {
  await connection.sendMessagePromise(messages.restartViseron());
};

export const getEntities = async (
  connection: Connection,
): Promise<types.Entities> =>
  connection.sendMessagePromise(messages.getEntities());

export const subscribeStates = async (
  connection: Connection,
  stateCallback: (stateChangedEvent: types.StateChangedEvent) => void,
  entity_id?: string,
  entity_ids?: string[],
  resubscribe = true,
) => {
  const storedStateCallback = stateCallback;
  const subscription = await connection.subscribeStates(
    storedStateCallback,
    entity_id,
    entity_ids,
    resubscribe,
  );
  return subscription;
};

export const subscribeEvent = async <T = types.Event>(
  connection: Connection,
  event: string,
  eventCallback: (event: T) => void,
) => {
  const subscription = await connection.subscribeEvent(
    event,
    eventCallback,
    true,
  );
  return subscription;
};

export const subscribeTimespans = async (
  connection: Connection,
  camera_identifiers: string[],
  date: string,
  timespanCallback: (message: types.HlsAvailableTimespans) => void,
  debounce?: number,
) => {
  const subscription = await connection.subscribeTimespans(
    timespanCallback,
    camera_identifiers,
    date,
    debounce,
    true,
  );
  return subscription;
};

export const useSubscribeTimespans = (
  camera_identifiers: string[],
  date: string | null,
  timespanCallback: (message: types.HlsAvailableTimespans) => void,
  enabled = true,
  debounce?: number,
) => {
  const viseron = useContext(ViseronContext);

  useEffect(() => {
    if (!enabled || !date) {
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
