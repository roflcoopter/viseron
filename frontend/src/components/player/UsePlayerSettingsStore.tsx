import { create } from "zustand";
import { persist } from "zustand/middleware";

interface PlayerSettingsState {
  mjpegPlayerMap: Record<string, boolean>;
  setMjpegPlayer: (cameraId: string, value: boolean) => void;
  drawObjectsMap: Record<string, boolean>;
  setDrawObjects: (cameraId: string, value: boolean) => void;
  drawMotionMap: Record<string, boolean>;
  setDrawMotion: (cameraId: string, value: boolean) => void;
  drawObjectMaskMap: Record<string, boolean>;
  setDrawObjectMask: (cameraId: string, value: boolean) => void;
  drawMotionMaskMap: Record<string, boolean>;
  setDrawMotionMask: (cameraId: string, value: boolean) => void;
  drawZonesMap: Record<string, boolean>;
  setDrawZones: (cameraId: string, value: boolean) => void;
  drawPostProcessorMaskMap: Record<string, boolean>;
  setDrawPostProcessorMask: (cameraId: string, value: boolean) => void;
}

export const usePlayerSettingsStore = create<PlayerSettingsState>()(
  persist(
    (set) => ({
      mjpegPlayerMap: {},
      setMjpegPlayer: (cameraId, value) =>
        set((state) => ({
          mjpegPlayerMap: { ...state.mjpegPlayerMap, [cameraId]: value },
        })),
      drawObjectsMap: {},
      setDrawObjects: (cameraId, value) =>
        set((state) => ({
          drawObjectsMap: { ...state.drawObjectsMap, [cameraId]: value },
        })),
      drawMotionMap: {},
      setDrawMotion: (cameraId, value) =>
        set((state) => ({
          drawMotionMap: { ...state.drawMotionMap, [cameraId]: value },
        })),
      drawObjectMaskMap: {},
      setDrawObjectMask: (cameraId, value) =>
        set((state) => ({
          drawObjectMaskMap: { ...state.drawObjectMaskMap, [cameraId]: value },
        })),
      drawMotionMaskMap: {},
      setDrawMotionMask: (cameraId, value) =>
        set((state) => ({
          drawMotionMaskMap: { ...state.drawMotionMaskMap, [cameraId]: value },
        })),
      drawZonesMap: {},
      setDrawZones: (cameraId, value) =>
        set((state) => ({
          drawZonesMap: { ...state.drawZonesMap, [cameraId]: value },
        })),
      drawPostProcessorMaskMap: {},
      setDrawPostProcessorMask: (cameraId, value) =>
        set((state) => ({
          drawPostProcessorMaskMap: {
            ...state.drawPostProcessorMaskMap,
            [cameraId]: value,
          },
        })),
    }),
    { name: "player-settings-store", version: 1 },
  ),
);
