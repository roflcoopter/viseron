import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import GitHubIcon from "@mui/icons-material/GitHub";
import HomeIcon from "@mui/icons-material/Home";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import { alpha, styled, useTheme } from "@mui/material/styles";
import * as React from "react";
import { Link } from "react-router-dom";

import { ColorModeContext } from "context/ColorModeContext";

const Header = styled("header")(({ theme }) => ({
  position: "sticky",
  top: 0,
  transition: theme.transitions.create("top"),
  zIndex: theme.zIndex.appBar,
  backdropFilter: "blur(20px)",
  boxShadow: `inset 0px -1px 1px ${
    theme.palette.mode === "dark"
      ? theme.palette.primary[900]
      : theme.palette.grey[300]
  }`,
  backgroundColor:
    theme.palette.mode === "dark"
      ? alpha(theme.palette.background.default, 0.72)
      : "rgba(255,255,255,0.72)",
  marginBottom: "10px",
}));

export default function AppHeader() {
  const colorMode = React.useContext(ColorModeContext);
  const theme = useTheme();

  return (
    <Header>
      <Container
        maxWidth={false}
        sx={{ display: "flex", alignItems: "center", minHeight: 56 }}
      >
        <Tooltip title="Home" enterDelay={300}>
          <IconButton component={Link} color="primary" to={"/"}>
            <HomeIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Box sx={{ ml: "auto" }} />
        <Stack direction="row" spacing={1}>
          <Tooltip title="GitHub" enterDelay={300}>
            <IconButton
              component="a"
              color="primary"
              target="_blank"
              href="https://github.com/roflcoopter/viseron"
            >
              <GitHubIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip
            title={
              theme.palette.mode === "dark"
                ? "In a Light mood today?"
                : "Join the Dark Side"
            }
            enterDelay={300}
          >
            <IconButton color="primary" onClick={colorMode.toggleColorMode}>
              {theme.palette.mode === "dark" ? (
                <Brightness7Icon />
              ) : (
                <Brightness4Icon />
              )}
            </IconButton>
          </Tooltip>
        </Stack>
      </Container>
    </Header>
  );
}
