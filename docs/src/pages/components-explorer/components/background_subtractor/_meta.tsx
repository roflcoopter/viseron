import { Component } from "@site/src/types";

const ComponentMetadata: Component = {
  title: "Background Subtractor",
  name: "background_subtractor",
  description:
    "Detects motion using OpenCV background subtraction algorithms for efficient video analysis.",
  image: "/img/logos/opencv.svg",
  tags: ["motion_detector"],
  category: null,
  path: "viseron/components/background_subtractor",
  issue: 'background_subtractor OR label:"component: background_subtractor" OR label:"domain: motion_detector"',
};

export default ComponentMetadata;
