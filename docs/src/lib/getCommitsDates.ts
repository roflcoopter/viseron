import data from "@site/src/generated/commitDates.json";

type CommitDates = {
  created?: string;
  updated?: string;
};

export default function useCommitDates(path: string): CommitDates {
  return data[path] ?? {};
}
