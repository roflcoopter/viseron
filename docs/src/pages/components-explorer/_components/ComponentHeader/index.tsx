import React from "react";

import Head from "@docusaurus/Head";

import { Component } from "@site/src/types";

import styles from "./styles.module.css";

function ComponentHeader({ meta }: { meta: Component }) {
  return (
    <div>
      <Head>
        <title>{meta.title} | Viseron</title>
      </Head>
      <div className={styles.header}>
        <h1>{meta.title}</h1>
        <img src={meta.image} alt={meta.title} />
      </div>
      <hr className="divider" />
    </div>
  );
}

export default React.memo(ComponentHeader);
