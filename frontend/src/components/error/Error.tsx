import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { ReactComponent as ViseronLogo } from "viseron-logo.svg";

interface ErrorProps {
  text: string;
}

export const Error = ({ text }: ErrorProps) => (
  <Box
    sx={{
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      gap: 2,
    }}
  >
    <ViseronLogo width={150} height={150} />
    <Typography variant="h5" align="center">
      {text}
    </Typography>
  </Box>
);

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

export const ErrorNotFound = () => (
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
