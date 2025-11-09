import { useMemo } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

import { useCameras, useCamerasFailed } from "lib/api/cameras";
import * as types from "lib/types";

type Cameras = {
  [key: string]: boolean;
};
interface CameraState {
  cameras: Cameras;
  selectedCameras: string[];
  toggleCamera: (cameraIdentifier: string) => void;
  selectSingleCamera: (cameraIdentifier: string) => void;
  selectionOrder: string[];
  setSelectedCameras: (cameras: string[]) => void;
  setSelectionOrder: (order: string[]) => void;
  swapCameraPositions: (sourceId: string, targetId: string) => void;
}

export const useCameraStore = create<CameraState>()(
  persist(
    (set) => ({
      cameras: {},
      selectedCameras: [],
      toggleCamera: (cameraIdentifier) => {
        set((state) => {
          const newCameras = { ...state.cameras };
          newCameras[cameraIdentifier] = !newCameras[cameraIdentifier];
          let newSelectionOrder = [...state.selectionOrder];
          if (newCameras[cameraIdentifier]) {
            newSelectionOrder.push(cameraIdentifier);
          } else {
            newSelectionOrder = newSelectionOrder.filter(
              (id) => id !== cameraIdentifier,
            );
          }
          return {
            cameras: newCameras,
            selectedCameras: Object.entries(newCameras)
              .filter(([_key, value]) => value)
              .map(([key]) => key),
            selectionOrder: newSelectionOrder,
          };
        });
      },
      selectSingleCamera: (cameraIdentifier) => {
        set((state) => {
          const newCameras = { ...state.cameras };
          Object.keys(newCameras).forEach((key) => {
            newCameras[key] = key === cameraIdentifier;
          });
          return {
            cameras: newCameras,
            selectedCameras: [cameraIdentifier],
            selectionOrder: [cameraIdentifier],
          };
        });
      },
      selectionOrder: [],
      setSelectedCameras: (cameras) => {
        set((state) => {
          const newCameras = { ...state.cameras };
          // Clear all cameras first
          Object.keys(newCameras).forEach((key) => {
            newCameras[key] = false;
          });
          // Set selected cameras
          cameras.forEach((cameraId) => {
            newCameras[cameraId] = true;
          });
          return {
            cameras: newCameras,
            selectedCameras: cameras,
          };
        });
      },
      setSelectionOrder: (order) => {
        set({ selectionOrder: order });
      },
      swapCameraPositions: (sourceId, targetId) => {
        set((state) => {
          const newSelectionOrder = [...state.selectionOrder];
          const sourceIndex = newSelectionOrder.indexOf(sourceId);
          const targetIndex = newSelectionOrder.indexOf(targetId);

          if (sourceIndex !== -1 && targetIndex !== -1) {
            // Swap positions in selection order
            [newSelectionOrder[sourceIndex], newSelectionOrder[targetIndex]] = [
              newSelectionOrder[targetIndex],
              newSelectionOrder[sourceIndex],
            ];
          }

          return {
            selectionOrder: newSelectionOrder,
          };
        });
      },
    }),
    { name: "camera-store" },
  ),
);

export const useFilteredCameras = () => {
  const camerasQuery = useCameras({});
  const failedCamerasQuery = useCamerasFailed({});

  // Combine the two queries into one object
  const cameraData: types.CamerasOrFailedCameras = useMemo(() => {
    if (!camerasQuery.data && !failedCamerasQuery.data) {
      return {};
    }
    return {
      ...camerasQuery.data,
      ...failedCamerasQuery.data,
    };
  }, [camerasQuery.data, failedCamerasQuery.data]);

  const { selectedCameras, selectionOrder } = useCameraStore();
  return useMemo(() => {
    // Return cameras ordered by selection order
    const orderedCameras: types.CamerasOrFailedCameras = {};

    // Add cameras in selection order
    selectionOrder.forEach((cameraId) => {
      if (selectedCameras.includes(cameraId) && cameraData[cameraId]) {
        orderedCameras[cameraId] = cameraData[cameraId];
      }
    });

    return orderedCameras;
  }, [cameraData, selectedCameras, selectionOrder]);
};
