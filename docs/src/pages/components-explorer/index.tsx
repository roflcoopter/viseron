// Modified version of https://github.com/facebook/docusaurus/blob/be0dc6b0c9d52e503dc1928f636010b761d5d44d/website/src/pages/showcase/index.tsx
import React, { useEffect, useMemo, useState } from "react";

import ExecutionEnvironment from "@docusaurus/ExecutionEnvironment";
import { useHistory, useLocation } from "@docusaurus/router";
import Heading from "@theme/Heading";
import Layout from "@theme/Layout";
import clsx from "clsx";

import { getIconComponent } from "@site/src/lib/iconMap";
import ComponentCard from "@site/src/pages/components-explorer/_components/ComponentCard";
import ComponentsTagSelect, {
  readSearchTags,
} from "@site/src/pages/components-explorer/_components/ComponentsTagSelect";
import componentList from "@site/src/pages/components-explorer/_importer";
import { Component, DomainType, Domains, DomainsList } from "@site/src/types";

import styles from "./styles.module.css";

const TITLE = "Components";
const DESCRIPTION = "Explore the components available in Viseron";

type UserState = {
  scrollTopPosition: number;
  focusedElementId: string | undefined;
};

export function prepareUserState(): UserState | undefined {
  if (ExecutionEnvironment.canUseDOM) {
    return {
      scrollTopPosition: window.scrollY,
      focusedElementId: document.activeElement?.id,
    };
  }

  return undefined;
}
const SearchNameQueryKey = "name";

function restoreUserState(userState: UserState | null) {
  const { scrollTopPosition, focusedElementId } = userState ?? {
    scrollTopPosition: 0,
    focusedElementId: undefined,
  };
  document.getElementById(focusedElementId)?.focus();
  window.scrollTo({ top: scrollTopPosition });
}

function readSearchName(search: string) {
  return new URLSearchParams(search).get(SearchNameQueryKey);
}

function filterComponents(
  components: Component[],
  selectedTags: DomainType[],
  searchName: string | null,
) {
  if (searchName) {
    // eslint-disable-next-line no-param-reassign
    components = components.filter((component) =>
      component.title.toLowerCase().includes(searchName.toLowerCase()),
    );
  }
  if (selectedTags.length === 0) {
    return components;
  }
  return components.filter((component) => {
    if (component.tags.length === 0) {
      return false;
    }
    return selectedTags.some((tag) => component.tags.includes(tag));
  });
}

function usefilteredComponents() {
  const location = useLocation<UserState>();
  // On SSR / first mount (hydration) no tag is selected
  const [selectedTags, setSelectedTags] = useState<DomainType[]>([]);
  const [searchName, setSearchName] = useState<string | null>(null);
  // Sync tags from QS to state (delayed on purpose to avoid SSR/Client
  // hydration mismatch)
  useEffect(() => {
    setSelectedTags(readSearchTags(location.search));
    setSearchName(readSearchName(location.search));
    restoreUserState(location.state);
  }, [location]);

  return useMemo(
    () =>
      filterComponents(Object.values(componentList), selectedTags, searchName),
    [selectedTags, searchName],
  );
}

function ComponentHeader() {
  return (
    <section className="margin-top--lg margin-bottom--lg text--center">
      <Heading as="h1">{TITLE}</Heading>
      <p>{DESCRIPTION}</p>
    </section>
  );
}

function ComponentFilters() {
  return (
    <section className="container margin-top--l margin-bottom--lg">
      <div className={clsx("margin-bottom--sm", styles.filterCheckbox)}>
        <div>
          <Heading as="h2">Filters</Heading>
        </div>
      </div>
      <ul className={clsx("clean-list", styles.checkboxList)}>
        {DomainsList.map((tag, i) => {
          const { label, color, icon } = Domains[tag];
          const id = `component_checkbox_id_${tag}`;
          const IconComponent = getIconComponent(icon);

          return (
            <li key={i} className={styles.checkboxListItem}>
              <ComponentsTagSelect
                tag={tag}
                id={id}
                label={label}
                icon={
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      marginLeft: 8,
                    }}
                  >
                    {IconComponent && (
                      <IconComponent size={16} style={{ color }} />
                    )}
                  </span>
                }
              />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function SearchBar() {
  const history = useHistory();
  const location = useLocation();
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    setValue(readSearchName(location.search));
  }, [location]);
  return (
    <div className={styles.searchContainer}>
      <input
        id="searchbar"
        placeholder="Search for component.."
        value={value ?? undefined}
        onInput={(e) => {
          setValue(e.currentTarget.value);
          const newSearch = new URLSearchParams(location.search);
          newSearch.delete(SearchNameQueryKey);
          if (e.currentTarget.value) {
            newSearch.set(SearchNameQueryKey, e.currentTarget.value);
          }
          history.push({
            ...location,
            search: newSearch.toString(),
            state: prepareUserState(),
          });
          setTimeout(() => {
            document.getElementById("searchbar")?.focus();
          }, 0);
        }}
      />
    </div>
  );
}

function ComponentCards({
  filteredComponents,
}: {
  filteredComponents: Component[];
}) {
  // Sort by first tag (type) according to DomainsList order
  const fallbackType = DomainsList[DomainsList.length - 1];
  const sortedComponents = [...filteredComponents].sort((a, b) => {
    const aType = (a.tags[0] as DomainType) ?? fallbackType;
    const bType = (b.tags[0] as DomainType) ?? fallbackType;
    return DomainsList.indexOf(aType) - DomainsList.indexOf(bType);
  });

  if (sortedComponents.length === 0) {
    return (
      <section className="margin-top--lg margin-bottom--xl">
        <div className="container padding-vert--md text--center">
          <Heading as="h2">No result</Heading>
          <SearchBar />
        </div>
      </section>
    );
  }

  return (
    <section className="margin-top--lg margin-bottom--xl">
      <div className="container">
        <div className={clsx("margin-bottom--md", styles.componentListHeader)}>
          <Heading as="h2">Components ({sortedComponents.length})</Heading>
          <SearchBar />
        </div>
        <ul className={clsx("clean-list", styles.componentList)}>
          {sortedComponents.map((component) => (
            <ComponentCard key={component.title} component={component} />
          ))}
        </ul>
      </div>
    </section>
  );
}

export default function Components(): JSX.Element {
  const filteredComponents = usefilteredComponents();
  return (
    <Layout title={TITLE} description={DESCRIPTION}>
      <main className="margin-vert--lg">
        <ComponentHeader />
        <ComponentFilters />
        <ComponentCards filteredComponents={filteredComponents} />
      </main>
    </Layout>
  );
}
