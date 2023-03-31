import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { ReactComponent as ViseronLogo } from "viseron-logo.svg";

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
        : undefined
    }
  >
    {fullScreen && (
      <Grid item>
        <Box display="flex" justifyContent="center" alignItems="center">
          <ViseronLogo width={150} height={150} />
        </Box>
      </Grid>
    )}
    <Grid item>
      <Box display="flex" justifyContent="center" alignItems="center">
        <CircularProgress />
      </Box>
    </Grid>
    <Grid item>
      <Box>
        <Typography align="center">{text}</Typography>
      </Box>
    </Grid>
  </Grid>
);
