/**
 * Get available labels that haven't been added yet
 * If availableLabels is provided (from API), filter out existing labels
 * If availableLabels is null/empty, return empty array to trigger text input mode
 */
export function getAvailableLabelsForAdd(
  existingLabels: string[],
  availableLabels: string[] | null | undefined,
): string[] {
  // If no available labels from API, return empty array (triggers text input mode)
  if (!availableLabels || availableLabels.length === 0) {
    return [];
  }

  // Filter out existing labels from available labels
  return availableLabels.filter((label) => !existingLabels.includes(label));
}
