export type DomainType =
  | "camera"
  | "nvr"
  | "system"
  | "protocol"
  | "notification"
  | "object_detector"
  | "motion_detector"
  | "image_classification"
  | "face_recognition"
  | "license_plate_recognition"
  | "integration";

export type Domain = {
  label: string;
  color: string;
  icon: string;
};

export type Component = {
  title: string;
  name: string;
  description: string;
  image: string;
  tags: DomainType[];
  category: string | null;
};

export const Domains: { [type in DomainType]: Domain } = {
  camera: {
    label: "Camera",
    color: "#8a7d1f",
    icon: "Camera",
  },

  nvr: {
    label: "NVR",
    color: "#142f66",
    icon: "Video",
  },

  system: {
    label: "System",
    color: "#156b6a",
    icon: "Chip",
  },

  protocol: {
    label: "Protocol",
    color: "#342a99",
    icon: "ConnectionSignal",
  },

  notification: {
    label: "Notification",
    color: "#991321",
    icon: "Notification",
  },

  object_detector: {
    label: "Object Detector",
    color: "#942f5c",
    icon: "GroupObjects",
  },

  motion_detector: {
    label: "Motion Detector",
    color: "#5a2469",
    icon: "Movement",
  },

  image_classification: {
    label: "Image Classification",
    color: "#993313",
    icon: "ImageReference",
  },

  face_recognition: {
    label: "Face Recognition",
    color: "#094446",
    icon: "FaceActivated",
  },

  license_plate_recognition: {
    label: "License Plate Recognition",
    color: "#440909",
    icon: "CarFront",
  },

  integration: {
    label: "Integration",
    color: "#2a9944",
    icon: "WirelessCheckout",
  },
};

export const DomainsList = Object.keys(Domains) as DomainType[];
