import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid2";
import Typography from "@mui/material/Typography";
import ViseronLogo from "svg/viseron-logo.svg?react";

interface LoadingProps {
  text: string;
  fullScreen?: boolean;
}

export const Loading = ({ text, fullScreen = true }: LoadingProps) => (
  <Grid
    container
    spacing={2}
    alignItems="center"
    justifyContent="center"
    direction="column"
    sx={
      fullScreen
        ? // Absolute positioning so loader does not move when header is shown
          {
            position: "absolute",
            top: "-20%",
            bottom: 0,
            margin: "auto 0",
            width: "100%",
          }
        : { marginTop: "10px" }
    }
  >
    {fullScreen && (
      <Grid>
        <Box display="flex" justifyContent="center" alignItems="center">
          <ViseronLogo
            width={150}
            height={150}
            role="img"
            aria-label="Viseron Logo"
          />
        </Box>
      </Grid>
    )}
    <Grid>
      <Box display="flex" justifyContent="center" alignItems="center">
        <CircularProgress />
      </Box>
    </Grid>
    <Grid>
      <Box>
        <Typography align="center">{text}</Typography>
      </Box>
    </Grid>
  </Grid>
);
