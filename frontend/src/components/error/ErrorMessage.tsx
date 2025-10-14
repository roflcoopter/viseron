import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grow from "@mui/material/Grow";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { Link } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

interface ErrorMessageProps {
  text: string;
  subtext?: string;
  image?: React.ReactNode;
}

export function ErrorMessage({ text, subtext, image }: ErrorMessageProps) {
  return (
    <Grow in appear>
      <Stack
        direction="row"
        justifyContent="center"
        alignItems="center"
        sx={{ width: 1, height: "70vh" }}
      >
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            gap: 2,
          }}
        >
          {image || <ViseronLogo width={150} height={150} />}
          <Typography variant="h5" align="center">
            {text}
          </Typography>
          {subtext && (
            <Typography variant="h6" align="center">
              {subtext}
            </Typography>
          )}
        </Box>
      </Stack>
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
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        gap: 2,
      }}
    >
      <Box
        sx={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
        }}
      >
        <FourIn404 />
        <ViseronLogo width={150} height={150} />
        <FourIn404 flip />
      </Box>
      <Typography variant="h5" align="center">
        Oops! The requested page was not found.
      </Typography>
    </Box>
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
  return (
    <Container
      sx={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        gap: 2,
        height: "100vh",
      }}
    >
      <ErrorMessage text="An error occurred" subtext={error.message} />
      <Button variant="contained" component={Link} to="/">
        Navigate to Home
      </Button>
      <Button variant="contained" onClick={resetErrorBoundary}>
        Retry
      </Button>
    </Container>
  );
}

export function ErrorBoundaryOuter({
  error,
  resetErrorBoundary,
}: ErrorBoundaryProps) {
  return (
    <Container
      sx={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        gap: 2,
        height: "100vh",
      }}
    >
      <ErrorMessage text="An error occurred" subtext={error.message} />
      <Button variant="contained" onClick={() => window.location.reload()}>
        Refresh
      </Button>
      <Button variant="contained" onClick={resetErrorBoundary}>
        Retry
      </Button>
    </Container>
  );
}
