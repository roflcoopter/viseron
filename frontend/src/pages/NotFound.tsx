import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";

import { ErrorNotFound } from "components/error/ErrorMessage";
import { BASE_PATH } from "lib/api/client";

function NotFound() {
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
      <Box
        sx={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
        }}
      >
        <ErrorNotFound />
      </Box>
      <Button variant="contained" component="a" href={`${BASE_PATH}/`}>
        Navigate to Home
      </Button>
    </Container>
  );
}

export default NotFound;
