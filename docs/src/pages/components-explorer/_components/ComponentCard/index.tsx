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
import {
  Component,
  Domain,
  DomainType,
  Domains,
  DomainsList,
} from "@site/src/types";

import styles from "./styles.module.css";

const TagComp = React.forwardRef<HTMLLIElement, Domain>(
  ({ label, color }, ref) => (
    <li ref={ref} className={styles.tag}>
      <span className={styles.textLabel}>{label.toLowerCase()}</span>
      <span className={styles.colorLabel} style={{ backgroundColor: color }} />
    </li>
  ),
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

function ComponentCard({ component }: { component: Component }) {
  const componentLink = `components-explorer/components/${component.name}`;
  return (
    <li key={component.title} className="card shadow--md outline">
      <Link href={componentLink}>
        <div className={clsx("card__image", styles.componentCardImage)}>
          <IdealImage img={component.image} alt={component.title} />
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
