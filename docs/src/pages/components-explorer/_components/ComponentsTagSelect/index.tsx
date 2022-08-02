// Modified version of https://github.com/facebook/docusaurus/blob/be0dc6b0c9d52e503dc1928f636010b761d5d44d/website/src/pages/showcase/_components/ShowcaseTagSelect/index.tsx
import React, {
  ComponentProps,
  ReactElement,
  ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";

import { useHistory, useLocation } from "@docusaurus/router";

import type { DomainType } from "@site/src/data/components";
import { prepareUserState } from "@site/src/pages/components-explorer";

import styles from "./styles.module.css";

interface Props extends ComponentProps<"input"> {
  icon: ReactElement<ComponentProps<"svg">>;
  label: ReactNode;
  tag: DomainType;
}
export function toggleListItem<T>(list: T[], item: T): T[] {
  const itemIndex = list.indexOf(item);
  if (itemIndex === -1) {
    return list.concat(item);
  }
  const newList = [...list];
  newList.splice(itemIndex, 1);
  return newList;
}

const TagQueryStringKey = "tags";

export function readSearchTags(search: string): DomainType[] {
  return new URLSearchParams(search).getAll(TagQueryStringKey) as DomainType[];
}

function replaceSearchTags(search: string, newTags: DomainType[]) {
  const searchParams = new URLSearchParams(search);
  searchParams.delete(TagQueryStringKey);
  newTags.forEach((tag) => searchParams.append(TagQueryStringKey, tag));
  return searchParams.toString();
}

function ComponentsTagSelect(
  { id, icon, label, tag, ...rest }: Props,
  ref: React.ForwardedRef<HTMLLabelElement>
) {
  const location = useLocation();
  const history = useHistory();
  const [selected, setSelected] = useState(false);
  useEffect(() => {
    const tags = readSearchTags(location.search);
    setSelected(tags.includes(tag));
  }, [tag, location]);
  const toggleTag = useCallback(() => {
    const tags = readSearchTags(location.search);
    const newTags = toggleListItem(tags, tag);
    const newSearch = replaceSearchTags(location.search, newTags);
    history.push({
      ...location,
      search: newSearch,
      state: prepareUserState(),
    });
  }, [tag, location, history]);
  return (
    <>
      <input
        type="checkbox"
        id={id}
        className="screen-reader-only"
        onChange={toggleTag}
        checked={selected}
        {...rest}
      />
      <label ref={ref} htmlFor={id} className={styles.checkboxLabel}>
        {label}
        {icon}
      </label>
    </>
  );
}

export default React.forwardRef(ComponentsTagSelect);
