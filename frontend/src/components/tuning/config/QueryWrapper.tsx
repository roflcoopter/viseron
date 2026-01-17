import { Alert, Box, LinearProgress, Typography } from "@mui/material";
import { ReactNode } from "react";

interface QueryWrapperProps {
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  showLoadingIndicator?: boolean;
  showErrorAlert?: boolean;
  showEmptyAlert?: boolean;
  loadingProgress?: number;
  title?: string;
  children: ReactNode;
}

/**
 * A wrapper component for handling query states (loading, error, empty).
 * Use this to standardize loading/error/empty handling across components.
 *
 * @param isLoading - Whether the query is loading
 * @param isError - Whether the query has an error
 * @param errorMessage - Custom error message to display
 * @param isEmpty - Whether the data is empty
 * @param emptyMessage - Custom empty message to display
 * @param showLoadingIndicator - Show loading progress bar (default: true)
 * @param showErrorAlert - Show error alert (default: true)
 * @param showEmptyAlert - Show empty alert (default: false, returns null instead)
 * @param loadingProgress - Progress value (0-100) for determinate mode (optional)
 * @param title - Section title to always display (optional)
 * @param children - Content to render when data is available
 */
export function QueryWrapper({
  isLoading,
  isError,
  errorMessage,
  isEmpty = false,
  emptyMessage = "No data available",
  showLoadingIndicator = true,
  showErrorAlert = true,
  showEmptyAlert = false,
  loadingProgress,
  title,
  children,
}: QueryWrapperProps) {
  const titleElement = title ? (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        mb: 1,
      }}
    >
      <Typography variant="subtitle2">{title}</Typography>
    </Box>
  ) : null;

  if (isLoading) {
    if (!showLoadingIndicator) {
      return null;
    }
    return (
      <Box sx={{ width: "100%" }}>
        {titleElement}
        <LinearProgress
          variant={
            loadingProgress !== undefined ? "determinate" : "indeterminate"
          }
          value={loadingProgress}
        />
      </Box>
    );
  }

  if (isError) {
    if (!showErrorAlert) {
      return null;
    }
    return (
      <Box>
        {titleElement}
        <Alert severity="error" variant="standard" sx={{ mb: 1, border: 0 }}>
          {errorMessage || "Failed to load data"}
        </Alert>
      </Box>
    );
  }

  if (isEmpty) {
    if (!showEmptyAlert) {
      return null;
    }
    return (
      <Box>
        {titleElement}
        <Alert severity="info" variant="standard" sx={{ mb: 1, border: 0 }}>
          {emptyMessage}
        </Alert>
      </Box>
    );
  }

  return children;
}
