import { Cube, LogoGithub } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { styled, useTheme } from "@mui/material/styles";
import { useContext } from "react";
import { useLocation } from "react-router-dom";

import { ViseronContext } from "context/ViseronContext";

const Footer = styled("footer")(() => ({
  position: "relative",
  left: 0,
  bottom: 0,
  paddingBottom: "30px",
}));

export default function AppFooter() {
  const theme = useTheme();
  const location = useLocation();
  const { version, gitCommit } = useContext(ViseronContext);
  const showFooter = !["/events", "/live", "/settings/configuration"].includes(
    location.pathname,
  );
  const isCamera = location.pathname.startsWith("/cameras");

  return showFooter ? (
    <Footer sx={{ paddingTop: isCamera ? "30px" : "60px" }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          flexDirection: { xs: "column", sm: "row" },
          flexWrap: "wrap",
          gap: { xs: 1, sm: 3 },
        }}
      >
        {/* Left side - Version info */}
        <Typography
          variant="body2"
          fontWeight="medium"
          color={theme.palette.text.secondary}
        >
          Viseron / {version} / {gitCommit}
        </Typography>

        {/* Right side - Links container */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 3,
          }}
        >
          {/* GitHub link */}
          <Link
            target="_blank"
            href="https://github.com/roflcoopter/viseron"
            color={theme.palette.text.secondary}
            variant="body2"
            sx={{
              fontWeight: "medium",
              display: "flex",
              alignItems: "center",
              textDecoration: "none",
              "&:hover": {
                textDecoration: "underline",
              },
            }}
          >
            <Box
              component="span"
              sx={{
                display: "inline-flex",
                alignItems: "center",
                marginRight: "5px",
              }}
            >
              <LogoGithub size={16} />
            </Box>
            GitHub
          </Link>

          {/* Components link */}
          <Link
            target="_blank"
            href="https://viseron.netlify.app/components-explorer"
            color={theme.palette.text.secondary}
            variant="body2"
            sx={{
              fontWeight: "medium",
              display: "flex",
              alignItems: "center",
              textDecoration: "none",
              "&:hover": {
                textDecoration: "underline",
              },
            }}
          >
            <Box
              component="span"
              sx={{
                display: "inline-flex",
                alignItems: "center",
                marginRight: "5px",
              }}
            >
              <Cube size={16} />
            </Box>
            Components
          </Link>
        </Box>
      </Box>

      {/* MIT License text and link */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          marginTop: 1,
          gap: 0.5,
        }}
      >
        <Typography
          component="span"
          variant="caption"
          color={theme.palette.text.secondary}
        >
          This software is licensed under the
        </Typography>
        <Link
          target="_blank"
          href="https://github.com/roflcoopter/viseron/blob/master/LICENSE"
          color={theme.palette.text.secondary}
          variant="caption"
          sx={{
            fontWeight: "medium",
            textDecoration: "none",
            "&:hover": {
              textDecoration: "underline",
            },
          }}
        >
          MIT License
        </Link>
      </Box>
    </Footer>
  ) : null;
}
