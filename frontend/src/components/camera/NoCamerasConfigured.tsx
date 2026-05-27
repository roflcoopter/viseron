import { Add } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

import { AddCameraDialog } from "components/camera/AddCameraDialog";

export function NoCamerasConfigured() {
  const navigate = useNavigate();
  const [addCameraOpen, setAddCameraOpen] = useState(false);

  return (
    <>
      <Grid
        container
        spacing={2}
        alignItems="center"
        justifyContent="center"
        direction="column"
        sx={{
          position: "absolute",
          top: "-20%",
          bottom: 0,
          margin: "auto 0",
          width: "100%",
        }}
      >
        <Grid>
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            sx={{ width: 150, height: 150 }}
          >
            <ViseronLogo
              width={150}
              height={150}
              role="img"
              aria-label="Viseron Logo"
            />
          </Box>
        </Grid>
        <Grid>
          <Typography align="center" variant="h6">
            No cameras configured
          </Typography>
        </Grid>
        <Grid>
          <Typography align="center" color="text.secondary">
            Add a camera component to your <Box component="code">config.yaml</Box>{" "}
            to get started.
          </Typography>
        </Grid>
        <Grid>
          <Box sx={{ display: "flex", gap: 1, justifyContent: "center" }}>
            <Button
              startIcon={<Add />}
              variant="contained"
              onClick={() => setAddCameraOpen(true)}
            >
              Add Camera
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate("/settings/configuration")}
            >
              Open Configuration Editor
            </Button>
          </Box>
        </Grid>
      </Grid>
      <AddCameraDialog
        open={addCameraOpen}
        onClose={() => setAddCameraOpen(false)}
      />
    </>
  );
}
