import { useMemo } from "react";

export function useFormChanges<T extends Record<string, any>>(
  currentValues: T,
  originalValues: T,
  customComparators?: Partial<
    Record<keyof T, (current: any, original: any) => boolean>
  >,
) {
  return useMemo(
    () =>
      (Object.keys(currentValues) as Array<keyof T>).some((key) => {
        const currentValue = currentValues[key];
        const originalValue = originalValues[key];

        // Use custom comparator if provided
        if (customComparators?.[key]) {
          return !customComparators[key]!(currentValue, originalValue);
        }

        // Default comparison
        return currentValue !== originalValue;
      }),
    [currentValues, originalValues, customComparators],
  );
}
