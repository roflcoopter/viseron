// Modified version of https://github.com/facebook/docusaurus/blob/be0dc6b0c9d52e503dc1928f636010b761d5d44d/website/src/pages/showcase/_components/ShowcaseCard/index.tsx
import React from "react";

import Link from "@docusaurus/Link";
import Heading from "@theme/Heading";
// This throws error in typechecking but works in runtime?
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import IdealImage from "@theme/IdealImage";
import clsx from "clsx";

import sortBy from "@site/src/lib/helpers";
import { getIconComponent } from "@site/src/lib/iconMap";
import {
  Component,
  Domain,
  DomainType,
  Domains,
  DomainsList,
} from "@site/src/types";

import styles from "./styles.module.css";

const TagComp = React.forwardRef<HTMLLIElement, Domain & { tag: DomainType }>(
  ({ label, color, icon }, ref) => {
    const IconComponent = getIconComponent(icon);

    return (
      <li
        ref={ref}
        className={styles.tag}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0px",
          padding: "4px 8px",
        }}
      >
        {IconComponent && <IconComponent size={14} style={{ color }} />}
        <span className={styles.textLabel}>{label.toLowerCase()}</span>
      </li>
    );
  },
);

function ComponentCardTag({ tags }: { tags: DomainType[] }) {
  const tagObjects = tags.map((tag) => ({ tag, ...Domains[tag] }));
  const tagObjectsSorted = sortBy(tagObjects, (tagObject) =>
    DomainsList.indexOf(tagObject.tag),
  );

  return (
    <>
      {tagObjectsSorted.map((tagObject, index) => (
        <TagComp key={index} {...tagObject} />
      ))}
    </>
  );
}

const BADGE_CATEGORIES = [
  {
    names: ["nvr"],
    label: "Required",
    style: {
      background: "#e53935",
      color: "#fff",
      borderRadius: 10,
      padding: "2px 8px",
      fontSize: 12,
      marginLeft: 8,
      fontWeight: 600,
    },
  },
  {
    names: ["ffmpeg", "gstreamer"],
    label: "Choose One",
    style: {
      background: "#fbc02d",
      color: "#222",
      borderRadius: 10,
      padding: "2px 8px",
      fontSize: 12,
      marginLeft: 8,
      fontWeight: 600,
    },
  },
  {
    names: ["webhook", "hailo"],
    label: "New",
    style: {
      background: "#43a047",
      color: "#fff",
      borderRadius: 10,
      padding: "2px 8px",
      fontSize: 12,
      marginLeft: 8,
      fontWeight: 600,
    },
  },
  {
    names: ["go2rtc"],
    label: "Featured",
    style: {
      background: "#1976d2",
      color: "#fff",
      borderRadius: 10,
      padding: "2px 8px",
      fontSize: 12,
      marginLeft: 8,
      fontWeight: 600,
    },
  },
];

function getBadge(name: string) {
  const categories = BADGE_CATEGORIES.find((cat) => cat.names.includes(name));
  if (!categories) return null;
  // Add a class for absolute positioning, but keep inline style for color etc.
  return (
    <span className={styles.componentCardBadge} style={categories.style}>
      {categories.label}
    </span>
  );
}

function ComponentCard({ component }: { component: Component }) {
  const componentLink = `/components-explorer/components/${component.name}`;
  const badge = getBadge(component.name);
  return (
    <li
      key={component.title}
      className={clsx(
        "card bg--secondary shadow--sm outline",
        styles.componentCardWrapper,
      )}
    >
      {badge}
      <Link href={componentLink}>
        <div className={clsx("card__image", styles.componentCardImage)}>
          <IdealImage
            img={component.image}
            alt={component.title}
            style={{
              maxHeight: 120,
              objectFit: "contain",
              width: "auto",
              margin: "0 auto",
              display: "block",
            }}
          />
        </div>
      </Link>
      <div className="card__body">
        <div className={clsx(styles.componentCardHeader)}>
          <Heading as="h4" className={styles.componentCardTitle}>
            <Link href={componentLink} className={styles.componentCardLink}>
              {component.title}
            </Link>
          </Heading>
        </div>
        <p className={styles.componentCardBody}>{component.description}</p>
      </div>
      <ul className={clsx("card__footer", styles.cardFooter)}>
        <ComponentCardTag tags={component.tags} />
      </ul>
    </li>
  );
}

export default React.memo(ComponentCard);
