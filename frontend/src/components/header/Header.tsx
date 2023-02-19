import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import GitHubIcon from "@mui/icons-material/GitHub";
import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import SettingsIcon from "@mui/icons-material/Settings";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import { alpha, styled, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useContext, useRef, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";

import { AuthContext } from "context/AuthContext";
import { ColorModeContext } from "context/ColorModeContext";
import { useScrollPosition } from "hooks/UseScrollPosition";
import { useToast } from "hooks/UseToast";
import { useAuthLogout } from "lib/api/auth";
import queryClient from "lib/api/client";

import { ReactComponent as ViseronLogo } from "../../viseron-logo.svg";
import Breadcrumbs from "./Breadcrumbs";

interface AppHeaderProps {
  setDrawerOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

interface HeaderProps {
  showHeader: boolean;
}

const Header = styled("header", {
  shouldForwardProp: (prop) => prop !== "showHeader",
})<HeaderProps>(({ theme, showHeader }) => ({
  position: "sticky",
  top: 0,
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
  transform: showHeader ? "translateY(0)" : "translateY(-100%)",
  transition: "transform 300ms ease-in",
}));

export default function AppHeader({ setDrawerOpen }: AppHeaderProps) {
  const colorMode = useContext(ColorModeContext);
  const theme = useTheme();
  const mediaQueryMedium = useMediaQuery(theme.breakpoints.up("md"));
  const [showHeader, setShowHeader] = useState(true);
  const lastTogglePos = useRef(0);
  const { auth } = useContext(AuthContext);

  useScrollPosition((prevPos: any, currPos: any) => {
    // Always show header if we haven't scrolled down more than theme.headerHeight
    if (currPos.y <= theme.headerHeight || lastTogglePos.current === 0) {
      lastTogglePos.current = currPos.y;
      setShowHeader(true);
      return;
    }

    // Dont toggle header visibility unless we scrolled up or down more than 20px
    const relativePosition = currPos.y - lastTogglePos.current;
    if (relativePosition > -20 && relativePosition < 20) {
      return;
    }

    if (currPos.y > prevPos.y) {
      // Scrolling down
      lastTogglePos.current = currPos.y;
      setShowHeader(false);
    } else if (currPos.y < prevPos.y) {
      // Scrolling up
      lastTogglePos.current = currPos.y;
      setShowHeader(true);
    }
  });

  const logout = useAuthLogout();
  const navigate = useNavigate();
  const toast = useToast();

  return (
    <Header showHeader={showHeader}>
      <Container
        maxWidth={false}
        sx={{
          display: "flex",
          alignItems: "center",
          minHeight: theme.headerHeight,
        }}
      >
        <Tooltip title="Menu" enterDelay={300}>
          <IconButton
            color="primary"
            onClick={() => {
              setDrawerOpen(true);
            }}
          >
            <MenuIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Home" enterDelay={300}>
          <Box
            component={RouterLink}
            to={"/"}
            aria-label="Home"
            sx={{ marginTop: "auto", marginLeft: "16px" }}
          >
            <ViseronLogo width={45} height={45} />
          </Box>
        </Tooltip>
        {mediaQueryMedium && <Breadcrumbs />}
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
          <Tooltip title={"Edit Configuration"} enterDelay={300}>
            <IconButton
              component={RouterLink}
              color="primary"
              to={"/configuration"}
            >
              <SettingsIcon />
            </IconButton>
          </Tooltip>
          {auth.enabled && (
            <Tooltip title={"Logout"} enterDelay={300}>
              <IconButton
                color="primary"
                onClick={() =>
                  logout.mutate(undefined, {
                    onSuccess: async (_data, _variables, _context) => {
                      queryClient.removeQueries();
                      toast.success("Successfully logged out");
                      navigate("/login");
                    },
                  })
                }
              >
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </Container>
    </Header>
  );
}
