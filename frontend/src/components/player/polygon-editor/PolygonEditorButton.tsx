import TuneIcon from "@mui/icons-material/Tune";
import { useCallback, useContext } from "react";

import { CustomFab } from "components/player/CustomControls";
import { ViseronContext } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import * as commands from "lib/commands";
import * as types from "lib/types";

import { parsePolygonsFromConfig } from "./configParser";
import { usePolygonEditorStore } from "./usePolygonEditorStore";

interface PolygonEditorButtonProps {
  camera: types.Camera | types.FailedCamera;
}

export function PolygonEditorButton({ camera }: PolygonEditorButtonProps) {
  const viseron = useContext(ViseronContext);
  const toast = useToast();
  const { isEditing, startEditing, stopEditing } = usePolygonEditorStore();

  const handleClick = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation();

      if (isEditing) {
        stopEditing();
        return;
      }

      if (!viseron.connection) {
        toast.error("Not connected to Viseron");
        return;
      }

      try {
        const config = await commands.getConfig(viseron.connection);
        const polygons = parsePolygonsFromConfig(config, camera.identifier);
        startEditing(camera.identifier, config, polygons);
      } catch (error) {
        toast.error(`Failed to load config: ${error}`);
      }
    },
    [
      isEditing,
      viseron.connection,
      camera.identifier,
      startEditing,
      stopEditing,
      toast,
    ],
  );

  return (
    <CustomFab onClick={handleClick}>
      <TuneIcon />
    </CustomFab>
  );
}
