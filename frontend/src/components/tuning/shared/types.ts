// Shared types for tuning components

export interface Camera {
  identifier: string;
  name: string;
  still_image: {
    width: number;
    height: number;
    available: boolean;
    refresh_interval?: number;
  };
}

export interface Coordinate {
  x: number;
  y: number;
}

export interface Mask {
  name?: string;
  coordinates: Coordinate[];
}

export interface BaseComponentData {
  componentType: string;
}

export interface TuneConfig {
  [domain: string]: {
    [component: string]: any;
  };
}
