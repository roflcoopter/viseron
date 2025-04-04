import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import SettingsIcon from "@mui/icons-material/Settings";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha, styled, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useContext, useRef, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

import Breadcrumbs from "components/header/Breadcrumbs";
import Drawer from "components/header/Drawer";
import { useAuthContext } from "context/AuthContext";
import { ColorModeContext } from "context/ColorModeContext";
import { ViseronContext } from "context/ViseronContext";
import { useScrollPosition } from "hooks/UseScrollPosition";
import { useToast } from "hooks/UseToast";
import { useAuthLogout } from "lib/api/auth";

interface HeaderProps {
  showHeader: boolean;
}

const Header = styled("header", {
  shouldForwardProp: (prop) => prop !== "showHeader",
})<HeaderProps>(({ theme }) => ({
  position: "sticky",
  top: 0,
  zIndex: theme.zIndex.appBar,
  backdropFilter: "blur(20px)",
  boxShadow: `inset 0px -1px 1px ${theme.palette.grey[300]}`,
  backgroundColor: "rgba(255,255,255,0.72)",
  marginBottom: theme.margin,
  transform: "translateY(-100%)",
  transition: "transform 300ms ease-in",
  ...theme.applyStyles("dark", {
    boxShadow: `inset 0px -1px 1px ${theme.palette.primary[900]}`,
    backgroundColor: alpha(theme.palette.background.default, 0.72),
  }),
  variants: [
    {
      props: ({ showHeader }) => showHeader,
      style: {
        transform: "translateY(0)",
      },
    },
  ],
}));

export default function AppHeader() {
  const colorMode = useContext(ColorModeContext);
  const theme = useTheme();
  const mediaQuerySmall = useMediaQuery(theme.breakpoints.up("sm"));
  const [showHeader, setShowHeader] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const lastTogglePos = useRef(0);
  const { auth, user } = useAuthContext();
  const { safeMode } = useContext(ViseronContext);

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
    <>
      <Drawer drawerOpen={drawerOpen} setDrawerOpen={setDrawerOpen} />
      <Header showHeader={showHeader}>
        <Container
          maxWidth={false}
          sx={{
            display: "flex",
            alignItems: "center",
            minHeight: theme.headerHeight,
          }}
        >
          <Stack
            direction="row"
            spacing={1}
            justifyContent="left"
            alignItems="center"
            sx={{ width: !mediaQuerySmall ? "12%" : undefined }}
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
                sx={{ marginLeft: "16px" }}
              >
                <ViseronLogo
                  width={45}
                  height={45}
                  style={{ marginTop: "4px" }}
                />
              </Box>
            </Tooltip>
          </Stack>
          <Box
            sx={
              !mediaQuerySmall
                ? { width: "76%", pointerEvents: "none" }
                : undefined
            }
          >
            <Breadcrumbs />
          </Box>
          <Stack
            direction="row"
            spacing={1}
            justifyContent="end"
            sx={{ width: !mediaQuerySmall ? "12%" : { marginLeft: "auto" } }}
          >
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
            {!auth.enabled || (auth.enabled && user?.role) === "admin" ? (
              <Tooltip title={"Settings"} enterDelay={300}>
                <IconButton
                  component={RouterLink}
                  color="primary"
                  to={"/settings"}
                >
                  <SettingsIcon />
                </IconButton>
              </Tooltip>
            ) : null}
            {auth.enabled && (
              <Tooltip title={"Logout"} enterDelay={300}>
                <IconButton
                  color="primary"
                  onClick={() =>
                    logout.mutate(undefined, {
                      onSuccess: async (_data, _variables, _context) => {
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
        {safeMode ? (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              gap: 2,
              backgroundColor: theme.palette.error.main,
            }}
          >
            <Typography
              align="center"
              style={{
                textShadow: "rgba(0, 0, 0, 1) 0px 0px 4px",
                margin: "5px",
              }}
            >
              Viseron is running in safe mode. Cameras are not loaded and no
              recordings are made. Please check the logs for more information.
            </Typography>
          </Box>
        ) : null}
      </Header>
    </>
  );
}
