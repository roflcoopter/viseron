import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import ViseronLogo from "svg/viseron-logo.svg?react";

interface LoadingProps {
  text: string;
  fullScreen?: boolean;
}

export function Loading({ text, fullScreen = true }: LoadingProps) {
  return (
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
          <Box 
            display="flex" 
            justifyContent="center" 
            alignItems="center"
            sx={{
              width: 150,
              height: 150,
              "& > *": {
                animation: "viseron-spin 2s linear infinite",
                transformOrigin: "center center",
                display: "block",
              },
              "@keyframes viseron-spin": {
                "0%": { transform: "rotate(0deg)" },
                "100%": { transform: "rotate(360deg)" },
              },
            }}
          >
            {/* SVG will inherit animation from parent Box */}
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
          <CircularProgress enableTrackSlot/>
        </Box>
      </Grid>
      <Grid>
        <Box>
          <Typography align="center">{text}</Typography>
        </Box>
      </Grid>
    </Grid>
  );
}
