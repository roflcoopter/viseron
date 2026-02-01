import { Alert, Box, LinearProgress, Typography } from "@mui/material";
import { ReactNode } from "react";

interface QueryWrapperProps {
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string | null;
  isWarning?: boolean;
  warningMessage?: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  showLoadingIndicator?: boolean;
  loadingProgress?: number;
  title?: string;
  children: ReactNode;
}

/**
 * A wrapper component for handling query states (loading, error, empty).
 * Use this to standardize loading/error/empty handling across components in Camera Tuning.
 *
 * @param isLoading - Whether the query is loading
 * @param isError - Whether the query has an error
 * @param errorMessage - Custom error message to display
 * @param isWarning - Whether to show a warning message
 * @param warningMessage - Custom warning message to display
 * @param isEmpty - Whether the data is empty
 * @param emptyMessage - Custom empty message to display
 * @param showLoadingIndicator - Show loading progress bar (default: true)
 * @param loadingProgress - Progress value (0-100) for determinate mode (optional)
 * @param title - Section title to always display (optional)
 * @param children - Content to render when data is available
 */
export function QueryWrapper({
  isLoading,
  isError,
  errorMessage,
  isWarning = false,
  warningMessage,
  isEmpty = false,
  emptyMessage = "No data available",
  showLoadingIndicator = true,
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
    return (
      <Box>
        {titleElement}
        <Alert severity="error" variant="standard" sx={{ border: 0 }}>
          {errorMessage || "Failed to load data"}
        </Alert>
      </Box>
    );
  }

  if (isWarning) {
    return (
      <Box>
        {titleElement}
        <Alert severity="warning" variant="standard" sx={{ border: 0 }}>
          {warningMessage || "Warning"}
        </Alert>
      </Box>
    );
  }

  if (isEmpty) {
    return (
      <Box>
        {titleElement}
        <Alert severity="info" variant="standard" sx={{ border: 0 }}>
          {emptyMessage}
        </Alert>
      </Box>
    );
  }

  return children;
}
