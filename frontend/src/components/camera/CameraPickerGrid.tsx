import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import { useTheme } from "@mui/material/styles";

import { CameraCard } from "components/camera/CameraCard";
import {
  useCameraStore,
  useFilteredCameras,
} from "components/camera/useCameraStore";
import { useCamerasAll } from "lib/api/cameras";
import * as types from "lib/types";

export function CameraPickerGrid() {
  const theme = useTheme();
  const { toggleCamera, selectionOrder } = useCameraStore();
  const camerasAll = useCamerasAll();
  const filteredCameras = useFilteredCameras();

  const handleCameraClick = (
    event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera | types.FailedCamera,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    toggleCamera(camera.identifier);
  };

  const getSelectionOrder = (cameraIdentifier: string): number | null => {
    const index = selectionOrder.indexOf(cameraIdentifier);
    return index !== -1 ? index + 1 : null;
  };

  return (
    <Grid container spacing={0.5}>
      {Object.keys(camerasAll.combinedData)
        .sort()
        .map((camera_identifier) => {
          const selectionNumber = getSelectionOrder(camera_identifier);
          const isSelected = filteredCameras &&
            Object.keys(filteredCameras).includes(camera_identifier);
          
          return (
            <Grow in appear key={camera_identifier}>
              <Grid
                key={camera_identifier}
                size={{
                  xs: 6,
                  sm: 6,
                  md: 3,
                  lg: 3,
                  xl: 3,
                }}
              >
                <Box sx={{ position: 'relative', width: '100%', height: '100%' }}>
                  <CameraCard
                    camera_identifier={camera_identifier}
                    compact
                    buttons={false}
                    onClick={(
                      event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
                    ) =>
                      handleCameraClick(
                        event,
                        camerasAll.combinedData[camera_identifier],
                      )
                    }
                    border={
                      isSelected
                        ? `2px solid ${theme.palette.primary[400]}`
                        : "2px solid transparent"
                    }
                  />
                  {isSelected && selectionNumber && (
                    <Chip
                      label={selectionNumber}
                      color="primary"
                      size="small"
                      sx={{
                        position: 'absolute',
                        bottom: 8,
                        right: 8,
                        minWidth: 24,
                        height: 24,
                        fontSize: '0.875rem',
                        fontWeight: 'bold',
                        zIndex: 2,
                        '& .MuiChip-label': {
                          padding: '0 6px',
                        },
                      }}
                    />
                  )}
                </Box>
              </Grid>
            </Grow>
          );
        })}
    </Grid>
  );
}
