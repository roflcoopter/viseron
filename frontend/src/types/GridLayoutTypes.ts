export type GridLayoutType = 
  | 'auto'           // No Grid - default adaptive layout
  | '3plus1'         // 3 Grid + 1 Slot
  | 'lshape'         // L shape + 1 main slot
  | 'square_center'  // Square + 1 main slot in center
  | '2plus1';        // 2 large on top + 1 large on bottom

export interface GridLayoutConfig {
  type: GridLayoutType;
  mainSlot?: string; // Camera identifier for main slot
  sideSlots?: string[]; // Camera identifiers for side slots
}

export interface GridLayoutSlot {
  id: string;
  position: {
    gridColumn: string;
    gridRow: string;
  };
  isMain?: boolean;
}

export const GRID_LAYOUT_NAMES: Record<GridLayoutType, string> = {
  auto: 'Auto Layout',
  '3plus1': '3 + 1 Layout', 
  lshape: 'L-Shape Layout',
  square_center: 'Square + Center',
  '2plus1': '2 + 1 Layout'
};