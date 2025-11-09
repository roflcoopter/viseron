import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import Grow from "@mui/material/Grow";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

interface ErrorMessageProps {
  text: string;
  subtext?: string;
  image?: React.ReactNode;
}

export function ErrorMessage({ text, subtext, image }: ErrorMessageProps) {
  return (
    <Grow in appear>
      <Container maxWidth="sm">
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            minHeight: "60vh",
            textAlign: "center",
            px: 2,
            pt: 4,
          }}
        >
          <Stack spacing={3} alignItems="center">
            {image || (
              <Box>
                <ViseronLogo width={120} height={120} />
              </Box>
            )}
            <Stack spacing={2} alignItems="center">
              <Typography
                variant="h4"
                component="h1"
                align="center"
                sx={{
                  fontWeight: 600,
                  color: "text.primary",
                  maxWidth: "600px",
                }}
              >
                {text}
              </Typography>
              {subtext && (
                <Typography
                  variant="body1"
                  align="center"
                  sx={{
                    color: "text.secondary",
                    maxWidth: "500px",
                    lineHeight: 1.6,
                  }}
                >
                  {subtext}
                </Typography>
              )}
            </Stack>
          </Stack>
        </Box>
      </Container>
    </Grow>
  );
}

function FourIn404({ flip }: { flip?: boolean }) {
  return (
    <Typography
      variant="h5"
      align="center"
      sx={{
        fontSize: "128px",
        ...(flip && { transform: "scaleX(-1)" }),
      }}
    >
      4
    </Typography>
  );
}

export function ErrorNotFound() {
  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "70vh",
          textAlign: "center",
          py: 4,
          pt: 6,
        }}
      >
        <Stack spacing={4} alignItems="center">
          <Box
            sx={{
              display: "flex",
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "center",
              gap: { xs: 0.5, sm: 1 },
            }}
          >
            <FourIn404 />
            <Box sx={{ mx: { xs: 1, sm: 2 } }}>
              <ViseronLogo width={120} height={120} />
            </Box>
            <FourIn404 flip />
          </Box>
          <Stack spacing={2} alignItems="center">
            <Typography
              variant="h4"
              component="h1"
              align="center"
              sx={{
                fontWeight: 600,
                color: "text.primary",
              }}
            >
              Page Not Found
            </Typography>
            <Typography
              variant="body1"
              align="center"
              sx={{
                color: "text.secondary",
                maxWidth: "500px",
                lineHeight: 1.6,
              }}
            >
              Oops! The requested page was not found. Please check the URL or
              navigate back to the home page.
            </Typography>
          </Stack>
        </Stack>
      </Box>
    </Container>
  );
}

interface ErrorBoundaryProps {
  error: Error;
  resetErrorBoundary: () => void;
}

export function ErrorBoundaryInner({
  error,
  resetErrorBoundary,
}: ErrorBoundaryProps) {
  const [isNavigating, setIsNavigating] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const navigate = useNavigate();

  const handleGoHome = () => {
    setIsNavigating(true);
    // Add small delay for smooth loading animation before client-side navigation
    setTimeout(() => {
      navigate("/");
    }, 300);
  };

  const handleTryAgain = () => {
    setIsRetrying(true);
    resetErrorBoundary();
  };

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "80vh",
          textAlign: "center",
          px: 2,
          pt: 4,
        }}
      >
        <Stack spacing={4} alignItems="center">
          <Stack spacing={3} alignItems="center">
            <Box>
              <ViseronLogo width={120} height={120} />
            </Box>
            <Stack spacing={2} alignItems="center">
              <Typography
                variant="h4"
                component="h1"
                align="center"
                sx={{
                  fontWeight: 600,
                  color: "text.primary",
                  maxWidth: "600px",
                }}
              >
                An error occurred
              </Typography>
              <Typography
                variant="body1"
                align="center"
                sx={{
                  color: "text.secondary",
                  maxWidth: "500px",
                  lineHeight: 1.6,
                }}
              >
                {error.message}
              </Typography>
            </Stack>
          </Stack>

          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={2}
            alignItems="center"
            justifyContent="center"
          >
            <Button
              variant="contained"
              onClick={handleGoHome}
              size="large"
              sx={{ minWidth: 120 }}
              disabled={isNavigating || isRetrying}
              startIcon={
                isNavigating ? (
                  <CircularProgress size={20} color="inherit" enableTrackSlot />
                ) : null
              }
            >
              Go Home
            </Button>
            <Button
              variant="outlined"
              onClick={handleTryAgain}
              size="large"
              sx={{ minWidth: 120 }}
              disabled={isNavigating || isRetrying}
              startIcon={
                isRetrying ? (
                  <CircularProgress size={20} color="inherit" enableTrackSlot />
                ) : null
              }
            >
              Try Again
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Container>
  );
}

export function ErrorBoundaryOuter({
  error,
  resetErrorBoundary,
}: ErrorBoundaryProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const navigate = useNavigate();

  const handleRefresh = () => {
    setIsRefreshing(true);
    // Add small delay for smooth loading animation before client-side navigation
    setTimeout(() => {
      navigate(0); // This refreshes the current route
    }, 300);
  };

  const handleTryAgain = () => {
    setIsRetrying(true);
    resetErrorBoundary();
  };

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "80vh",
          textAlign: "center",
          px: 2,
          pt: 4,
        }}
      >
        <Stack spacing={4} alignItems="center">
          <Stack spacing={3} alignItems="center">
            <Box>
              <ViseronLogo width={120} height={120} />
            </Box>
            <Stack spacing={2} alignItems="center">
              <Typography
                variant="h4"
                component="h1"
                align="center"
                sx={{
                  fontWeight: 600,
                  color: "text.primary",
                  maxWidth: "600px",
                }}
              >
                An error occurred
              </Typography>
              <Typography
                variant="body1"
                align="center"
                sx={{
                  color: "text.secondary",
                  maxWidth: "500px",
                  lineHeight: 1.6,
                }}
              >
                {error.message}
              </Typography>
            </Stack>
          </Stack>

          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={2}
            alignItems="center"
            justifyContent="center"
          >
            <Button
              variant="contained"
              onClick={handleRefresh}
              size="large"
              sx={{ minWidth: 120 }}
              disabled={isRefreshing || isRetrying}
              startIcon={
                isRefreshing ? (
                  <CircularProgress size={20} color="inherit" enableTrackSlot />
                ) : null
              }
            >
              Refresh Page
            </Button>
            <Button
              variant="outlined"
              onClick={handleTryAgain}
              size="large"
              sx={{ minWidth: 120 }}
              disabled={isRefreshing || isRetrying}
              startIcon={
                isRetrying ? (
                  <CircularProgress size={20} color="inherit" enableTrackSlot />
                ) : null
              }
            >
              Try Again
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Container>
  );
}
