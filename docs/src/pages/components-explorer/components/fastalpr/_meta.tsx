import { Component } from "@site/src/types";

const ComponentMetadata: Component = {
  title: "fastALPR",
  name: "fastalpr",
  description:
    "Local, in-process license plate recognition using ONNX models. No external server required.",
  // fast-alpr itself has no project logo, but it runs its detector/OCR models
  // through ONNX Runtime under the hood, so that logo is used instead.
  image: "/img/logos/onnxruntime.png",
  tags: ["license_plate_recognition"],
  category: "new",
  path: "viseron/components/fastalpr",
  issue: 'fastalpr OR label:"component: fastalpr"',
};

export default ComponentMetadata;
