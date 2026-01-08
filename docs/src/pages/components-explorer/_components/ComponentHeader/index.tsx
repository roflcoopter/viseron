import React from "react";
import { Debug, LogoGithub } from "@carbon/icons-react";
import Head from "@docusaurus/Head";
import Link from "@docusaurus/Link";
import Heading from "@theme/Heading";

import useCommitDates from "@site/src/lib/getCommitsDates";
import { getIconComponent } from "@site/src/lib/iconMap";
import { Component, DomainType, Domains } from "@site/src/types";

import styles from "./styles.module.css";

function TagBadge({ tag }: { tag: DomainType }) {
  const { label, color, icon } = Domains[tag];
  const IconComponent = getIconComponent(icon);
  return (
    <span
      style={{
        background: "transparent",
        border: `1px solid ${color}`,
        borderRadius: 10,
        padding: "2px 8px",
        fontSize: 12,
        marginRight: 8,
        marginBottom: 4,
        fontWeight: 400,
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
      }}
      title={label}
    >
      {IconComponent && (
        <IconComponent size={14} style={{ color, marginRight: 3 }} />
      )}
      {label}
    </span>
  );
}

function ComponentHeader({ meta }: { meta: Component }) {
  const { created, updated } = useCommitDates(meta.path);

  return (
    <div>
      <Head>
        <title>{meta.title} | Viseron</title>
      </Head>
      <div className={styles.header}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
            flex: 1,
          }}
        >
          <Heading as="h1" style={{ marginBottom: 10 }}>
            {meta.title}
          </Heading>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              marginBottom: 0,
            }}
          >
            {meta.tags &&
              meta.tags.map((tag) => <TagBadge key={tag} tag={tag} />)}
          </div>
        </div>
        <img src={meta.image} alt={meta.title} />
      </div>
      <hr className="divider" style={{ marginBottom: 10 }} />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            columnGap: 20,
          }}
        >
          <div
            style={{
              color: "gray",
            }}
          >
            Created: {created ? new Date(created).toLocaleDateString() : "—"}
          </div>
          <div
            style={{
              color: "gray",
            }}
          >
            Updated: {updated ? new Date(updated).toLocaleDateString() : "—"}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            columnGap: 20,
          }}
        >
          <Link
            href={`https://github.com/roflcoopter/viseron/tree/master/${meta.path}`}
            style={{
              display: "flex",
              alignItems: "center",
            }}
          >
            <LogoGithub />
            &nbsp;View source on Github
          </Link>
          <Link
            href={`https://github.com/roflcoopter/viseron/issues?q=${meta.issue}`}
            style={{
              display: "flex",
              alignItems: "center",
            }}
          >
            <Debug />
            &nbsp;View all issues
          </Link>
        </div>
      </div>
      <hr className="divider" style={{ marginTop: 10 }} />
    </div>
  );
}

export default React.memo(ComponentHeader);
