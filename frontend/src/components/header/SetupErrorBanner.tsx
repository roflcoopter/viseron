import { Warning } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useContext } from "react";
import { Link as RouterLink } from "react-router-dom";

import { ViseronContext } from "context/ViseronContext";

export default function SetupErrorBanner() {
  const theme = useTheme();
  const { setupStatus } = useContext(ViseronContext);

  const errorCount = setupStatus.components.reduce(
    (sum, comp) => sum + comp.errors.length + (comp.validation_error ? 1 : 0),
    0,
  );

  if (errorCount === 0) {
    return null;
  }

  const getSummary = () =>
    errorCount === 1
      ? "1 setup error detected."
      : `${errorCount} setup errors detected.`;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "row",
        justifyContent: "center",
        alignItems: "center",
        gap: 1,
        paddingX: 2,
        paddingY: 0.5,
        color: theme.palette.error.contrastText,
        background: theme.palette.error.main,
      }}
    >
      <Warning size={16} />
      <Typography variant="body2" align="center" fontWeight={500}>
        {getSummary()}{" "}
        <Typography
          component={RouterLink}
          to="/settings/configuration"
          variant="body2"
          color="inherit"
          fontWeight={700}
        >
          {errorCount > 1
            ? "View all errors in Configuration Editor"
            : "View in Configuration Editor"}
        </Typography>
      </Typography>
    </Box>
  );
}
