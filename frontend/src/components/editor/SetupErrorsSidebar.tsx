import {
  ChevronDown,
  ChevronUp,
  ErrorFilled,
  WarningAltFilled,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import Collapse from "@mui/material/Collapse";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { type Palette, alpha, useTheme } from "@mui/material/styles";
import { useContext, useState } from "react";

import { ViseronContext } from "context/ViseronContext";
import type { SetupError } from "lib/types";

function getSourceColor(source: string, palette: Palette) {
  switch (source) {
    case "validation":
    case "import":
      return palette.error.main;
    case "domain":
      return palette.warning.main;
    case "setup":
    case "setup_domains":
      return palette.error.light;
    default:
      return palette.grey[500];
  }
}

function getSourceLabel(source: string) {
  switch (source) {
    case "validation":
      return "Validation";
    case "setup":
      return "Setup";
    case "setup_domains":
      return "Domain Setup";
    case "domain":
      return "Domain";
    case "import":
      return "Import";
    default:
      return source;
  }
}

function ErrorItem({ error }: { error: SetupError }) {
  const theme = useTheme();
  const sourceColor = getSourceColor(error.source, theme.palette);
  const isRetrying = error.source === "domain";

  return (
    <Box
      sx={{
        padding: 1.5,
        borderLeft: `3px solid ${sourceColor}`,
        backgroundColor: alpha(sourceColor, 0.04),
        ...theme.applyStyles("dark", {
          backgroundColor: alpha(sourceColor, 0.08),
        }),
        "&:hover": {
          backgroundColor: alpha(sourceColor, 0.08),
          ...theme.applyStyles("dark", {
            backgroundColor: alpha(sourceColor, 0.12),
          }),
        },
        transition: "background-color 0.2s ease",
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
        {isRetrying ? (
          <WarningAltFilled size={14} color={theme.palette.warning.main} />
        ) : (
          <ErrorFilled size={14} color={theme.palette.error.main} />
        )}
        <Typography
          variant="caption"
          sx={{ fontWeight: 700, color: "text.primary" }}
        >
          {error.component_name || "Unknown"}
        </Typography>
        <Chip
          label={getSourceLabel(error.source)}
          size="small"
          sx={{
            height: 18,
            fontSize: "0.65rem",
            fontWeight: 600,
            backgroundColor: alpha(sourceColor, 0.15),
            color: sourceColor,
            ...theme.applyStyles("dark", {
              backgroundColor: alpha(sourceColor, 0.2),
            }),
          }}
        />
      </Stack>
      {(error.domain || error.identifier) && (
        <Typography
          variant="caption"
          sx={{ color: "text.secondary", display: "block", mb: 0.25 }}
        >
          {error.domain}
          {error.identifier && ` / ${error.identifier}`}
        </Typography>
      )}
      <Typography
        variant="body2"
        sx={{
          color: "text.secondary",
          fontSize: "0.8rem",
          lineHeight: 1.4,
          wordBreak: "break-word",
        }}
      >
        {error.message}
      </Typography>
    </Box>
  );
}

export default function SetupErrorsSidebar() {
  const theme = useTheme();
  const { setupStatus } = useContext(ViseronContext);
  const [collapsed, setCollapsed] = useState(false);

  // Derive errors from component and validation errors
  const allErrors: SetupError[] = [];
  for (const comp of setupStatus.components) {
    for (const err of comp.errors) {
      allErrors.push(err);
    }
    if (comp.validation_error) {
      allErrors.push({
        source: "validation",
        message: comp.validation_error,
        component_name: comp.name,
      });
    }
  }

  if (allErrors.length === 0) {
    return null;
  }

  const errorCount = allErrors.length;

  return (
    <Card
      variant="outlined"
      sx={{
        height: "100%",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        borderColor: alpha(theme.palette.error.main, 0.3),
        ...theme.applyStyles("dark", {
          borderColor: alpha(theme.palette.error.main, 0.2),
        }),
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 1.5,
          py: 1,
          background: alpha(theme.palette.error.main, 0.4),
          borderBottom: `1px solid ${alpha(theme.palette.error.main, 0.15)}`,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <ErrorFilled size={16} color={theme.palette.error.main} />
          <Typography
            variant="subtitle2"
            sx={{ fontWeight: 700, color: "text.primary" }}
          >
            Setup Errors
          </Typography>
          <Chip
            label={errorCount}
            size="small"
            color="error"
            sx={{
              height: 20,
              fontSize: "0.7rem",
              fontWeight: 700,
            }}
          />
        </Stack>
        <IconButton size="small" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </IconButton>
      </Box>
      <Collapse
        in={!collapsed}
        sx={{ flex: 1, minHeight: 0, overflowY: "auto" }}
      >
        <Stack divider={<Divider />}>
          {allErrors.map((error) => (
            <ErrorItem
              key={`${error.component_name}-${error.domain}-${error.identifier}-${error.source}-${error.message}`}
              error={error}
            />
          ))}
        </Stack>
      </Collapse>
    </Card>
  );
}
