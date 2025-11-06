import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { GridLayoutConfig, GridLayoutType } from "types/GridLayoutTypes";

export interface View {
  id: string;
  name: string;
  layoutType: GridLayoutType;
  layoutConfig: GridLayoutConfig;
  selectedCameras: string[];
  selectionOrder: string[];
  createdAt: number;
}

interface ViewStore {
  views: View[];
  addView: (view: Omit<View, 'id' | 'createdAt'>) => void;
  removeView: (id: string) => void;
  updateView: (id: string, updates: Partial<Omit<View, 'id' | 'createdAt'>>) => void;
  loadView: (id: string) => View | null;
  clearViews: () => void;
}

export const useViewStore = create<ViewStore>()(
  persist(
    (set, get) => ({
      views: [],

      addView: (viewData) => {
        const newView: View = {
          ...viewData,
          id: Date.now().toString(),
          createdAt: Date.now(),
        };
        
        set((state) => ({
          views: [...state.views, newView].slice(0, 5), // Max 5 views
        }));
      },

      removeView: (id) => {
        set((state) => ({
          views: state.views.filter(view => view.id !== id),
        }));
      },

      updateView: (id, updates) => {
        set((state) => ({
          views: state.views.map(view => 
            view.id === id ? { ...view, ...updates } : view
          ),
        }));
      },

      loadView: (id) => {
        const state = get();
        return state.views.find(view => view.id === id) || null;
      },

      clearViews: () => {
        set({ views: [] });
      },
    }),
    {
      name: 'view-store',
      version: 1,
    }
  )
);