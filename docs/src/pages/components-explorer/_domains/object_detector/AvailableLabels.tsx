import React from "react";

import Admonition from "@theme/Admonition";
import CodeBlock from "@theme/CodeBlock";

type AvailableLabelsProps = {
  showLabels?: boolean;
  labelPath?: string;
  extras?: React.ReactNode;
};

function AvailableLabels({
  showLabels = true,
  labelPath,
  extras,
}: AvailableLabelsProps) {
  if (showLabels && labelPath)
    return (
      <div>
        <Admonition type="tip">
          To see the default available labels you can inspect the{" "}
          <code>label_path</code> file.
          <CodeBlock language="bash">
            docker exec -it viseron cat {labelPath}
          </CodeBlock>
        </Admonition>
      </div>
    );
  if (showLabels && !labelPath)
    throw new Error("labelPath is required if showLabels is true");
  if (extras) return <div>{extras}</div>;
}

export default AvailableLabels;
