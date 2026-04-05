import { create } from "zustand";

import { Point, Polygon } from "./types";

interface PolygonEditorState {
  isEditing: boolean;
  polygons: Polygon[];
  originalPolygons: Polygon[];
  selectedPolygonId: string | null;
  hoveredVertexInfo: { polygonId: string; vertexIndex: number } | null;
  isDirty: boolean;
  isSaving: boolean;
  rawYamlConfig: string | null;
  cameraIdentifier: string | null;

  // Actions
  startEditing: (
    cameraId: string,
    config: string,
    polygons: Polygon[],
  ) => void;
  stopEditing: () => void;
  selectPolygon: (id: string | null) => void;
  moveVertex: (polygonId: string, vertexIndex: number, newPoint: Point) => void;
  addVertex: (polygonId: string, afterIndex: number, point: Point) => void;
  deleteVertex: (polygonId: string, vertexIndex: number) => void;
  addPolygon: (polygon: Polygon) => void;
  deletePolygon: (id: string) => void;
  updatePolygonName: (id: string, name: string) => void;
  revert: () => void;
  setSaving: (saving: boolean) => void;
  setRawYamlConfig: (config: string) => void;
}

export const usePolygonEditorStore = create<PolygonEditorState>((set) => ({
  isEditing: false,
  polygons: [],
  originalPolygons: [],
  selectedPolygonId: null,
  hoveredVertexInfo: null,
  isDirty: false,
  isSaving: false,
  rawYamlConfig: null,
  cameraIdentifier: null,

  startEditing: (cameraId, config, polygons) =>
    set({
      isEditing: true,
      cameraIdentifier: cameraId,
      rawYamlConfig: config,
      polygons,
      originalPolygons: JSON.parse(JSON.stringify(polygons)),
      selectedPolygonId: null,
      isDirty: false,
      isSaving: false,
    }),

  stopEditing: () =>
    set({
      isEditing: false,
      polygons: [],
      originalPolygons: [],
      selectedPolygonId: null,
      hoveredVertexInfo: null,
      isDirty: false,
      isSaving: false,
      rawYamlConfig: null,
      cameraIdentifier: null,
    }),

  selectPolygon: (id) => set({ selectedPolygonId: id }),

  moveVertex: (polygonId, vertexIndex, newPoint) =>
    set((state) => ({
      polygons: state.polygons.map((p) =>
        p.id === polygonId
          ? {
              ...p,
              points: p.points.map((pt, i) =>
                i === vertexIndex ? newPoint : pt,
              ),
            }
          : p,
      ),
      isDirty: true,
    })),

  addVertex: (polygonId, afterIndex, point) =>
    set((state) => ({
      polygons: state.polygons.map((p) =>
        p.id === polygonId
          ? {
              ...p,
              points: [
                ...p.points.slice(0, afterIndex + 1),
                point,
                ...p.points.slice(afterIndex + 1),
              ],
            }
          : p,
      ),
      isDirty: true,
    })),

  deleteVertex: (polygonId, vertexIndex) =>
    set((state) => ({
      polygons: state.polygons.map((p) => {
        if (p.id !== polygonId || p.points.length <= 3) return p;
        return {
          ...p,
          points: p.points.filter((_, i) => i !== vertexIndex),
        };
      }),
      isDirty: true,
    })),

  addPolygon: (polygon) =>
    set((state) => ({
      polygons: [...state.polygons, polygon],
      selectedPolygonId: polygon.id,
      isDirty: true,
    })),

  deletePolygon: (id) =>
    set((state) => ({
      polygons: state.polygons.filter((p) => p.id !== id),
      selectedPolygonId:
        state.selectedPolygonId === id ? null : state.selectedPolygonId,
      isDirty: true,
    })),

  updatePolygonName: (id, name) =>
    set((state) => ({
      polygons: state.polygons.map((p) => (p.id === id ? { ...p, name } : p)),
      isDirty: true,
    })),

  revert: () =>
    set((state) => ({
      polygons: JSON.parse(JSON.stringify(state.originalPolygons)),
      selectedPolygonId: null,
      isDirty: false,
    })),

  setSaving: (saving) => set({ isSaving: saving }),

  setRawYamlConfig: (config) => set({ rawYamlConfig: config }),
}));
