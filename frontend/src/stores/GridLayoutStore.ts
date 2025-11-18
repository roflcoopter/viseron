import type { GridLayoutConfig, GridLayoutType } from "types/GridLayoutTypes";
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface GridLayoutStore {
  currentLayout: GridLayoutType;
  layoutConfig: GridLayoutConfig;
  setLayout: (layout: GridLayoutType) => void;
  setCurrentLayout: (layout: GridLayoutType) => void;
  setLayoutConfig: (config: GridLayoutConfig) => void;
  setMainSlot: (cameraId: string) => void;
  setSideSlots: (cameraIds: string[]) => void;
  resetLayout: () => void;
}

export const useGridLayoutStore = create<GridLayoutStore>()(
  persist(
    (set, _get) => ({
      currentLayout: "auto",
      layoutConfig: {
        type: "auto",
        mainSlot: undefined,
        sideSlots: [],
      },

      setLayout: (layout: GridLayoutType) => {
        set((state) => ({
          currentLayout: layout,
          layoutConfig: {
            ...state.layoutConfig,
            type: layout,
            // Reset slots when changing layout type
            mainSlot:
              layout === "auto" ? undefined : state.layoutConfig.mainSlot,
            sideSlots: layout === "auto" ? [] : state.layoutConfig.sideSlots,
          },
        }));
      },

      setCurrentLayout: (layout: GridLayoutType) => {
        set({ currentLayout: layout });
      },

      setLayoutConfig: (config: GridLayoutConfig) => {
        set({ layoutConfig: config });
      },

      setMainSlot: (cameraId: string) => {
        set((state) => ({
          layoutConfig: {
            ...state.layoutConfig,
            mainSlot: cameraId,
          },
        }));
      },

      setSideSlots: (cameraIds: string[]) => {
        set((state) => ({
          layoutConfig: {
            ...state.layoutConfig,
            sideSlots: cameraIds,
          },
        }));
      },

      resetLayout: () => {
        set({
          currentLayout: "auto",
          layoutConfig: {
            type: "auto",
            mainSlot: undefined,
            sideSlots: [],
          },
        });
      },
    }),
    {
      name: "grid-layout-store",
      version: 1,
    },
  ),
);
