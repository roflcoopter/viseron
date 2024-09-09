import { UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useContext, useEffect } from "react";

import { ViseronContext } from "context/ViseronContext";
import queryClient, { viseronAPI } from "lib/api/client";
import { subscribeRecordingStart, subscribeRecordingStop } from "lib/commands";
import * as types from "lib/types";

type RecordingsVariables = {
  camera_identifier: string | null;
  date?: string;
  latest?: boolean;
  daily?: boolean;
  failed?: boolean;
  configOptions?: Omit<
    UseQueryOptions<types.RecordingsCamera, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};
async function recordings({
  camera_identifier,
  date,
  latest,
  daily,
  failed,
}: RecordingsVariables) {
  const response = await viseronAPI.get<types.RecordingsCamera>(
    `recordings/${camera_identifier}${date ? `/${date}` : ""}`,
    {
      params: {
        ...(latest ? { latest } : null),
        ...(daily ? { daily } : null),
        ...(failed ? { failed } : null),
      },
    },
  );
  return response.data;
}

export const useRecordings = ({
  camera_identifier,
  date,
  latest,
  daily,
  failed,
  configOptions,
}: RecordingsVariables) => {
  const { connection } = useContext(ViseronContext);

  useEffect(() => {
    const unsub: Array<() => void> = [];
    if (connection && camera_identifier) {
      const invalidate = (
        recordingEvent: types.EventRecorderStart | types.EventRecorderStop,
      ) => {
        queryClient.invalidateQueries({
          queryKey: ["recordings", recordingEvent.data.camera.identifier],
        });
      };

      const subscribe = async () => {
        unsub.push(
          await subscribeRecordingStart(
            connection,
            invalidate,
            camera_identifier,
          ),
        );
        unsub.push(
          await subscribeRecordingStop(
            connection,
            invalidate,
            camera_identifier,
          ),
        );
      };
      subscribe();
    }
    return () => {
      unsub.forEach((u) => u());
      unsub.length = 0; // clear array
    };
  }, [camera_identifier, connection]);

  if (camera_identifier === null && configOptions?.enabled) {
    throw new Error(
      "camera_identifier can only be null while query is disabled",
    );
  }

  return useQuery({
    queryKey: ["recordings", camera_identifier, date, latest, daily, failed],
    queryFn: async () =>
      recordings({ camera_identifier, date, latest, daily, failed }),
    ...configOptions,
  });
};
