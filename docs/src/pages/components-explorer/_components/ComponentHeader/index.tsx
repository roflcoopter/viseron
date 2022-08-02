import React from "react";

import Head from "@docusaurus/Head";

import { Component } from "@site/src/types";

function ComponentHeader({ meta }: { meta: Component }) {
  return (
    <div>
      <Head>
        <title>{meta.title} | Viseron</title>
      </Head>
      <h1>{meta.title}</h1>
      <hr className="divider" />
    </div>
  );
}

export default React.memo(ComponentHeader);
