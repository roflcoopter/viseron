import React from "react";

import Head from "@docusaurus/Head";
import Heading from "@theme/Heading";

import { Component } from "@site/src/types";

import styles from "./styles.module.css";

function ComponentHeader({ meta }: { meta: Component }) {
  return (
    <div>
      <Head>
        <title>{meta.title} | Viseron</title>
      </Head>
      <div className={styles.header}>
        <Heading as="h1">{meta.title}</Heading>
        <img src={meta.image} alt={meta.title} />
      </div>
      <hr className="divider" />
    </div>
  );
}

export default React.memo(ComponentHeader);
