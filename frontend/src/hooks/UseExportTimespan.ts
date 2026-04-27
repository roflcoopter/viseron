import { useContext } from "react";

import { ViseronContext } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import { exportTimespan } from "lib/commands";

export const useExportTimespan = () => {
  const viseron = useContext(ViseronContext);
  const toast = useToast();

  const exportTimespanCallback = async (
    camera_identifiers: string[],
    start: number,
    end: number,
  ) => {
    if (!viseron.connection) {
      return;
    }

    await exportTimespan(
      viseron.connection,
      camera_identifiers,
      start,
      end,
      toast,
    );
  };

  return exportTimespanCallback;
};
