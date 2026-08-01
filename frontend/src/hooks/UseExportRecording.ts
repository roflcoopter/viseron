import { useContext } from "react";

import { ViseronContext } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import { exportRecording } from "lib/commands";

export const useExportRecording = () => {
  const viseron = useContext(ViseronContext);
  const toast = useToast();

  const exportRecordingCallback = async (
    camera_identifier: string,
    recording_id: number,
  ) => {
    if (!viseron.connection) {
      return;
    }

    await exportRecording(
      viseron.connection,
      camera_identifier,
      recording_id,
      toast,
    );
  };

  return exportRecordingCallback;
};
