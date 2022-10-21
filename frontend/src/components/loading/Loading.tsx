import { Typography } from "@mui/material";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";

interface LoadingProps {
  text: string;
}

export const Loading = ({ text }: LoadingProps) => (
  <Container>
    <Grid container justifyContent="center">
      <Box>
        <CircularProgress />
      </Box>
    </Grid>
    <Box>
      <Typography align="center">{text}</Typography>
    </Box>
  </Container>
);
