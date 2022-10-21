import React from "react";

import Admonition from "@theme/Admonition";
import CodeBlock from "@theme/CodeBlock";

function AvailableLabels({ labelPath }) {
  return labelPath ? (
    <div>
      <Admonition type="tip">
        To see the default available labels you can inspect the{" "}
        <code>label_path</code> file.
        <CodeBlock language="bash">
          docker exec -it viseron cat {labelPath}
        </CodeBlock>
      </Admonition>
    </div>
  ) : null;
}

export default AvailableLabels;
