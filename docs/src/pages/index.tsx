import React from "react";

import useBaseUrl from "@docusaurus/useBaseUrl";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import Layout from "@theme/Layout";
import clsx from "clsx";

import HomepageFeatures from "@site/src/components/HomepageFeatures";

import styles from "./index.module.css";

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <header className={clsx("hero hero--primary", styles.heroBanner)}>
      <div className="container">
        <div className="row">
          <div className={clsx("col col--5")}>
            <img
              className={styles.heroLogo}
              alt="Viseron Logo"
              src={useBaseUrl("/img/viseron-logo.svg")}
            />
          </div>
          <div className={clsx("col col--5")}>
            <h1 className={styles.heroTitle}>{siteConfig.title}</h1>
            <p className={styles.heroTagline}>{siteConfig.tagline}</p>
            <p>
              <div className={styles.heroText}>
                With features such as:<br></br>
                Object Detection<br></br>
                Motion Detection<br></br>
                Face Recognition<br></br>
                Image Classification<br></br>
                License Plate Recognition<br></br>
                Hardware Acceleration
              </div>
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}

export default function Home(): JSX.Element {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout title={`Homepage`} description={siteConfig.tagline}>
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
