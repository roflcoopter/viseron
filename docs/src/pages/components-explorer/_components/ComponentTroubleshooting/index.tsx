import React from "react";

import CodeBlock from "@theme/CodeBlock";

import { Component } from "@site/src/types";

function ComponentTroubleshooting({
  meta,
  logs,
}: {
  meta: Component;
  logs?: string[] | undefined;
}) {
  return (
    <div>
      To enable debug logging for <code>{meta.name}</code>, add the following to
      your <code>config.yaml</code>
      <CodeBlock language="yaml" title="/config/config.yaml">
        {`logger:
  logs:
    viseron.components.${meta.name}: debug
`}
        {logs?.map((log) => `    ${log}: debug\n`)}
      </CodeBlock>
    </div>
  );
}

export default ComponentTroubleshooting;
