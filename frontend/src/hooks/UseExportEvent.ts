import { useContext } from "react";

import { ViseronContext } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import { exportRecording, exportSnapshot } from "lib/commands";
import * as types from "lib/types";

export const useExportEvent = () => {
  const viseron = useContext(ViseronContext);
  const toast = useToast();

  const exportEvent = async (event: types.CameraEvent) => {
    if (!viseron.connection) {
      return event;
    }

    switch (event.type) {
      case "object":
      case "face_recognition":
      case "license_plate_recognition":
      case "motion":
        await exportSnapshot(
          viseron.connection,
          event.type,
          event.camera_identifier,
          event.id,
          toast,
        );
        return event;

      case "recording":
        await exportRecording(
          viseron.connection,
          event.camera_identifier,
          event.id,
          toast,
        );
        return event;

      default:
        return event satisfies never;
    }
  };

  return exportEvent;
};
