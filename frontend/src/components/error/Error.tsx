import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { ReactComponent as ViseronLogo } from "viseron-logo.svg";

interface ErrorProps {
  text: string;
}

export const Error = ({ text }: ErrorProps) => (
  <Grid
    container
    spacing={2}
    alignItems="center"
    justifyContent="center"
    direction="column"
    sx={{
      marginTop: "30%",
      marginBottom: 5,
    }}
  >
    <Grid item>
      <Box display="flex" justifyContent="center" alignItems="center">
        <ViseronLogo width={150} height={150} />
      </Box>
    </Grid>
    <Grid item>
      <Box>
        <Typography variant="h5" align="center">
          {text}
        </Typography>
      </Box>
    </Grid>
  </Grid>
);
