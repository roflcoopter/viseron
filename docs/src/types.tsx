export type DomainType =
  | "camera"
  | "face_recognition"
  | "image_classification"
  | "motion_detector"
  | "nvr"
  | "object_detector";

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

  face_recognition: {
    label: "Face Recognition",
    color: "#127f82",
  },

  image_classification: {
    label: "Image Classification",
    color: "#fe6829",
  },

  motion_detector: {
    label: "Motion Detector",
    color: "#a44fb7",
  },

  nvr: {
    label: "NVR",
    color: "#3063ca",
  },

  object_detector: {
    label: "Object Detector",
    color: "#e9669e",
  },
};

export const DomainsList = Object.keys(Domains) as DomainType[];
