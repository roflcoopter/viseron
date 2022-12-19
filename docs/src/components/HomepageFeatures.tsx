import React from "react";

import useBaseUrl from "@docusaurus/useBaseUrl";
import clsx from "clsx";

import styles from "./HomepageFeatures.module.css";

type FeatureItem = {
  title: string;
  image: string;
  description: JSX.Element;
};

const FeatureList: FeatureItem[] = [
  {
    title: "Simple to Setup",
    image: "/img/undraw_setup.svg",
    description: (
      <>
        Just spin up the Docker-container and fill in the{" "}
        <code>config.yaml</code> using the integrated editor.
      </>
    ),
  },
  {
    title: "Highly Customizable",
    image: "/img/undraw_advanced_customization.svg",
    description: (
      <>
        Viseron comes with a good number of components which can be mixed and
        matched to your liking.<br></br>
        <a href="/components-explorer">See full list of components here.</a>
      </>
    ),
  },
  {
    title: "Hardware Accelerated",
    image: "/img/undraw_speed_test.svg",
    description: (
      <>
        Viseron supports CUDA, Google Coral EdgeTPU and Jetson Nano, among
        others, to better utilize your systems resources.
      </>
    ),
  },
];

function Feature({ title, image, description }: FeatureItem) {
  return (
    <div className={clsx("col col--4")}>
      <div className="text--center">
        <img
          className={styles.featureSvg}
          alt={title}
          src={useBaseUrl(image)}
        />
      </div>
      <div className="text--center padding-horiz--md">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): JSX.Element {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
