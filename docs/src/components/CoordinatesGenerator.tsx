import React, { useState } from "react";

import CodeBlock from "@theme/CodeBlock";
import yaml from "js-yaml";

import { Component } from "@site/src/types";

const CoordinatesGenerator = (props: {
  meta: Component;
  domain: "object_detector" | "motion_detector";
}) => {
  const placeholder = "522,11,729,275,333,603,171,97";
  const [value, setValue] = useState<string>();
  const [error, setError] = useState<string>();
  const [generatedYaml, setGeneratedYaml] = useState<string>();

  const onClick = () => {
    // Split the string into an array of individual coordinate values
    setError(undefined);
    setGeneratedYaml(undefined);
    const coordinateArray = value.split(",");

    if (coordinateArray.length % 2 !== 0) {
      setError("Invalid coordinate string, must be even number of values");
      return;
    }

    if (coordinateArray.length < 6) {
      setError(
        "Invalid coordinate string, must be at least 3 pairs (6 in total) of values"
      );
      return;
    }

    const configObject = {};
    // Convert the array into a YAML list of dictionaries
    const coordinates = {
      mask: [
        {
          coordinates: [],
        },
      ],
    };

    for (let i = 0; i < coordinateArray.length; i += 2) {
      const x = Number(coordinateArray[i]);
      const y = Number(coordinateArray[i + 1]);
      coordinates.mask[0].coordinates.push({ x, y });
    }

    const component = props.meta.name ? props.meta.name : "<component>";
    configObject[component] = {};
    configObject[component][props.domain.toString()] = {
      cameras: {
        camera_one: coordinates,
      },
    };
    const yamlString = yaml.dump(configObject, {
      noCompatMode: true,
    });
    setGeneratedYaml(yamlString);
  };

  return (
    <div>
      <p>
        Paste your coordinates here and press <code>Get config</code> to
        generate a config example
      </p>
      <input
        placeholder={placeholder}
        onInput={(ev) => setValue((ev.target as HTMLInputElement).value)}
        style={{ width: "80%", display: "inline-block", marginRight: 16 }}
      />
      <button
        onClick={() => {
          onClick();
        }}
        style={{ cursor: value ? "pointer" : "default" }}
        disabled={!value}
      >
        Get config
      </button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {generatedYaml && <CodeBlock language="yaml">{generatedYaml}</CodeBlock>}
    </div>
  );
};

export default CoordinatesGenerator;
