import {
  Camera,
  CarFront,
  Chip,
  ConnectionSignal,
  FaceActivated,
  WatsonHealth3DMprToggle,
  VisualRecognition,
  Movement,
  Notification,
  Video,
  WirelessCheckout,
} from "@carbon/icons-react";
import type { CarbonIconType } from "@carbon/icons-react";

export const iconMap: Record<string, CarbonIconType> = {
  Camera,
  CarFront,
  ConnectionSignal,
  FaceActivated,
  WatsonHealth3DMprToggle,
  VisualRecognition,
  Movement,
  Notification,
  Chip,
  Video,
  WirelessCheckout,
};

export const getIconComponent = (iconName: string) => iconMap[iconName];
