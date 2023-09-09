import Box from "@mui/material/Box";
import Grow from "@mui/material/Grow";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { ReactComponent as ViseronLogo } from "svg/viseron-logo.svg";

interface ErrorProps {
  text: string;
  image?: React.ReactNode;
}

export const Error = ({ text, image }: ErrorProps) => (
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
      </Box>
    </Stack>
  </Grow>
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
