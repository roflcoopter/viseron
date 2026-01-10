import React from "react";

import {
  Camera,
  CarFront,
  Chip,
  Demo,
  FaceActivated,
  GroupObjects,
  CheckmarkOutline,
  ImageReference,
  Movement,
  Video,
} from "@carbon/icons-react";
import Link from "@docusaurus/Link";
import useBaseUrl from "@docusaurus/useBaseUrl";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import Heading from "@theme/Heading";
import Layout from "@theme/Layout";
import clsx from "clsx";

import HomepageFeatures from "@site/src/components/HomepageFeatures";

import styles from "./index.module.css";

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <header className={clsx("hero hero--primary", styles.heroBanner)}>
      <div className="container">
        <div className={clsx("row")}>
          <div className={clsx("col col--5")}>
            <div className={styles.logoContainer}>
              <img
                className={styles.heroLogo}
                alt="Viseron Logo"
                src={useBaseUrl("/img/viseron-logo.svg")}
              />
              <Heading as="h1" className={styles.heroTitle}>
                {siteConfig.title}
              </Heading>
              <p className={styles.heroTagline}>{siteConfig.tagline}</p>
            </div>
          </div>
          <div className={clsx("col col--7")}>
            <Heading as="h2" className={styles.featuresHeading}>
              With Modern Built In Features
            </Heading>
            <div className={styles.featuresGrid}>
              <Link
                to="/docs/documentation/configuration/domains/#camera-domain"
                className={styles.featureItem}
              >
                <Camera size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>Camera Agnostic</div>
                  <div className={styles.featureDesc}>
                    Works with any camera brand or type
                  </div>
                </div>
              </Link>
              <Link to="/components-explorer/components/onvif" className={styles.featureItem}>
                <CheckmarkOutline size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>ONVIF Compatible</div>
                  <div className={styles.featureDesc}>
                    Control and configure ONVIF cameras
                  </div>
                </div>
              </Link>
              <Link
                to="/components-explorer?tags=object_detector"
                className={styles.featureItem}
              >
                <GroupObjects size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>Object Detection</div>
                  <div className={styles.featureDesc}>
                    Detect and track objects in real-time
                  </div>
                </div>
              </Link>
              <Link
                to="/components-explorer?tags=motion_detector"
                className={styles.featureItem}
              >
                <Movement size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>Motion Detection</div>
                  <div className={styles.featureDesc}>
                    Smart motion detection with filters
                  </div>
                </div>
              </Link>
              <Link
                to="/components-explorer?tags=face_recognition"
                className={styles.featureItem}
              >
                <FaceActivated size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>Face Recognition</div>
                  <div className={styles.featureDesc}>
                    Identify known and unknown faces
                  </div>
                </div>
              </Link>
              <Link
                to="/components-explorer?tags=image_classification"
                className={styles.featureItem}
              >
                <ImageReference size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>
                    Image Classification
                  </div>
                  <div className={styles.featureDesc}>
                    Classify images using AI models
                  </div>
                </div>
              </Link>
              <Link
                to="/components-explorer?tags=license_plate_recognition"
                className={styles.featureItem}
              >
                <CarFront size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>
                    License Plate Recognition
                  </div>
                  <div className={styles.featureDesc}>
                    Read and track vehicle plates
                  </div>
                </div>
              </Link>
              <Link
                to="/docs/documentation/installation#supported-architectures"
                className={styles.featureItem}
              >
                <Chip size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>
                    Hardware Acceleration
                  </div>
                  <div className={styles.featureDesc}>
                    GPU, NPU, and TPU support
                  </div>
                </div>
              </Link>
              <Link
                to="/docs/documentation/configuration/live_view"
                className={styles.featureItem}
              >
                <Video size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>Advanced Live View</div>
                  <div className={styles.featureDesc}>
                    Low-latency streaming with WebRTC
                  </div>
                </div>
              </Link>
              <Link
                to="/docs/documentation/configuration/recordings"
                className={styles.featureItem}
              >
                <Demo size={32} className={styles.featureIcon} />
                <div>
                  <div className={styles.featureTitle}>24/7 Recordings</div>
                  <div className={styles.featureDesc}>
                    Continuous recording with retention
                  </div>
                </div>
              </Link>
            </div>
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
