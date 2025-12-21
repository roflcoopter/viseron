// Camera domain specific types

export type VideoTransformType = "hflip" | "vflip" | "rotate180";
export type VideoTransformTarget = "camera" | "recorder";

export interface VideoTransform {
  id: string;
  type: VideoTransformTarget;
  transform: VideoTransformType;
}

export interface OSDText {
  id: string;
  type: "camera" | "recorder";
  textType: "timestamp" | "custom" | "text";
  customText?: string;
  position: "top-left" | "top-right" | "bottom-left" | "bottom-right";
  paddingX: number;
  paddingY: number;
  fontSize: number;
  fontColor: string;
  boxColor: string;
}

export interface CameraComponentData {
  componentType: string;
  osd_texts?: OSDText[];
  video_transforms?: VideoTransform[];
  video_filters?: string[];
  recorder?: {
    video_filters?: string[];
  };
}
