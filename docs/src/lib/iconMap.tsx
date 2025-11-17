import {
  Camera,
  CarFront,
  Chip,
  ConnectionSignal,
  FaceActivated,
  GroupObjects,
  ImageReference,
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
  GroupObjects,
  ImageReference,
  Movement,
  Notification,
  Chip,
  Video,
  WirelessCheckout,
};

export const getIconComponent = (iconName: string) => iconMap[iconName];
