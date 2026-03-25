export interface Camera {
  still_image: {
    width: number;
    height: number;
  };
}

export interface Coordinate {
  x: number;
  y: number;
}

export interface ZoneData {
  name: string;
  coordinates: Coordinate[];
}

export interface MaskData {
  name: string;
  coordinates: Coordinate[];
}

export interface OSDTextData {
  id: string;
  type: "camera" | "recorder";
  textType: "timestamp" | "custom" | "text";
  customText: string;
  position: string;
  paddingX: number;
  paddingY: number;
  fontSize: number;
  fontColor: string;
  boxColor: string;
}

export interface VideoTransformData {
  id: string;
  type: "camera" | "recorder";
  transform: "hflip" | "vflip" | "rotate180";
}

export interface ComponentData {
  zones?: ZoneData[];
  mask?: MaskData[];
  osd_texts?: OSDTextData[];
  video_transforms?: VideoTransformData[];
}

export interface DragHandlers {
  onPointDrag?: (
    type: "zone" | "mask",
    itemIndex: number,
    pointIndex: number,
    newX: number,
    newY: number,
  ) => void;
  onPolygonDrag?: (
    type: "zone" | "mask",
    itemIndex: number,
    deltaX: number,
    deltaY: number,
    imageWidth: number,
    imageHeight: number,
  ) => void;
}
