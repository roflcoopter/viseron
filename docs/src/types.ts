export type DomainType =
  | "camera"
  | "face_recognition"
  | "image_classification"
  | "license_plate_recognition"
  | "motion_detector"
  | "notification"
  | "nvr"
  | "object_detector"
  | "system";

export type Domain = {
  label: string;
  color: string;
};

export type Component = {
  title: string;
  name: string;
  description: string;
  image: string;
  tags: DomainType[];
};

export const Domains: { [type in DomainType]: Domain } = {
  camera: {
    label: "Camera",
    color: "#dfd545",
  },

  system: {
    label: "System",
    color: "#30cac8",
  },

  nvr: {
    label: "NVR",
    color: "#3063ca",
  },

  notification: {
    label: "Notification",
    color: "#ff2a44",
  },

  face_recognition: {
    label: "Face Recognition",
    color: "#127f82",
  },

  image_classification: {
    label: "Image Classification",
    color: "#fe6829",
  },

  license_plate_recognition: {
    label: "License Plate Recognition",
    color: "#821212",
  },

  motion_detector: {
    label: "Motion Detector",
    color: "#a44fb7",
  },

  object_detector: {
    label: "Object Detector",
    color: "#e9669e",
  },
};

export const DomainsList = Object.keys(Domains) as DomainType[];
