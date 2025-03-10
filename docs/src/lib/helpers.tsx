// Copied from https://github.com/facebook/docusaurus/blob/be0dc6b0c9d52e503dc1928f636010b761d5d44d/website/src/utils/jsUtils.ts#L9-L19
export default function sortBy<T>(
  array: T[],
  getter: (item: T) => string | number | boolean,
): T[] {
  const sortedArray = [...array];
  sortedArray.sort((a, b) =>
    // eslint-disable-next-line no-nested-ternary
    getter(a) > getter(b) ? 1 : getter(b) > getter(a) ? -1 : 0,
  );
  return sortedArray;
}
