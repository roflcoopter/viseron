import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebars: SidebarsConfig = {
  docs: [
    "documentation",
    {
      type: "category",
      label: "Installation",
      link: {
        type: "doc",
        id: "documentation/installation",
      },
      collapsed: false,
      items: [
        {
          type: "link",
          label: "Supported architectures",
          href: "/docs/documentation/installation#supported-architectures",
        },
        {
          type: "link",
          label: "Running Viseron",
          href: "/docs/documentation/installation#running-viseron",
        },
        {
          type: "link",
          label: "User and Group Identifiers",
          href: "/docs/documentation/installation#user-and-group-identifiers",
        },
      ],
    },
    {
      type: "category",
      label: "Configuration",
      link: {
        type: "doc",
        id: "documentation/configuration",
      },
      collapsed: false,
      items: [
        { type: "doc", id: "documentation/configuration/components" },
        {
          type: "category",
          label: "Domains",
          link: {
            type: "doc",
            id: "documentation/configuration/domains/index",
          },
          collapsed: false,
          items: [
            {
              type: "link",
              label: "Camera",
              href: "/docs/documentation/configuration/domains/#camera-domain",
            },
            {
              type: "link",
              label: "Object Detector",
              href: "/docs/documentation/configuration/domains/#object-detector-domain",
            },
            {
              type: "link",
              label: "Motion Detector",
              href: "/docs/documentation/configuration/domains/#motion-detector-domain",
            },
            {
              type: "link",
              label: "Face Recognition",
              href: "/docs/documentation/configuration/domains/#face-recognition-domain",
            },
            {
              type: "link",
              label: "Image Classification",
              href: "/docs/documentation/configuration/domains/#image-classification-domain",
            },
            {
              type: "link",
              label: "License Plate Recognition",
              href: "/docs/documentation/configuration/domains/#license-plate-recognition-domain",
            },
          ],
        },
        { type: "doc", id: "documentation/configuration/secrets" },
      ],
    },
  ],
  contributing: [{}],
  backend: [
    "developers",
    {
      type: "category",
      label: "Development Environment",
      items: [
        "developers/development_environment/setup",
        "developers/development_environment/style_guidelines",
        "developers/development_environment/pull_request",
      ],
    },
    {
      type: "category",
      label: "Backend",
      link: {
        type: "doc",
        id: "developers/backend",
      },
      items: [
        "developers/backend/components",
        "developers/backend/data_stream_component",
        "developers/backend/domains",
        "developers/backend/entities",
        "developers/backend/events",
        "developers/backend/vis_object",
        "developers/backend/create_component",
      ],
    },
    {
      type: "category",
      label: "Frontend",
      link: {
        type: "doc",
        id: "developers/frontend",
      },
      items: ["developers/frontend/proxy"],
    },
    "developers/docker",
    {
      type: "category",
      label: "Docs",
      link: {
        type: "doc",
        id: "developers/docs",
      },
      items: ["developers/docs"],
    },
  ],
};

export default sidebars;
