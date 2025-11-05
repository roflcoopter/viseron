import {
  LogoGithub,
  IntrusionPrevention,
  VideoChat,
  Book,
  Settings,
  Demo,
  Video,
  TableSplit,
  Roadmap,
  Need,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import ListSubheader from "@mui/material/ListSubheader";
import Typography from "@mui/material/Typography";
import { Link, Location, useLocation } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";
import { useContext } from "react";

import { useAuthContext } from "context/AuthContext";
import { ViseronContext } from "context/ViseronContext";
import * as types from "lib/types";

type DrawerItemHeader = { type: "header"; title: string };

type DrawerItemLink = {
  type: "link";
  path: string;
  title: string;
  icon: React.ComponentType<{ size?: number | string }>;
  external?: boolean;
};

type DrawerItemDivider = { type: "divider" };

type DrawerItemTypes = DrawerItemHeader | DrawerItemLink | DrawerItemDivider;

const getDrawerItems = (
  auth: types.AuthEnabledResponse,
  user: types.AuthUserResponse | null,
) => {
  const drawerItems: Array<DrawerItemTypes> = [
    { type: "header", title: "Pages" },
    { type: "link", title: "Cameras", icon: Video, path: "/" },
    {
      type: "link",
      title: "Recordings",
      icon: Demo,
      path: "/recordings",
    },
    {
      type: "link",
      title: "Events",
      icon: IntrusionPrevention,
      path: "/events?tab=events",
    },
    {
      type: "link",
      title: "Timeline",
      icon: Roadmap,
      path: "/events?tab=timeline",
    },
    {
      type: "link",
      title: "Live View",
      icon: VideoChat,
      path: "/live",
    },
    { type: "link", title: "Entities", icon: TableSplit, path: "/entities" },
    ...(!auth.enabled || (auth.enabled && user?.role === "admin")
      ? [
          { type: "divider" } as DrawerItemTypes,
          { type: "header", title: "Administration" } as DrawerItemTypes,
          {
            type: "link",
            title: "Settings",
            icon: Settings,
            path: "/settings",
          } as DrawerItemTypes,
        ]
      : []),
    { type: "divider" },
    { type: "header", title: "Links" },
    {
      type: "link",
      title: "GitHub",
      icon: LogoGithub,
      path: "https://github.com/roflcoopter/viseron",
      external: true,
    },
    {
      type: "link",
      title: "Documentation",
      icon: Book,
      path: "https://viseron.netlify.app",
      external: true,
    },
    {
      type: "link",
      title: "Donations",
      icon: Need,
      path: "https://github.com/sponsors/roflcoopter",
      external: true,
    },
    { type: "divider" },
  ];
  return drawerItems;
};

interface AppDrawerProps {
  drawerOpen: boolean;
  setDrawerOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

function AppDrawerHeader() {
  const { version } = useContext(ViseronContext);

  return (
    <Container
      fixed
      disableGutters
      sx={(theme) => ({
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        paddingRight: "10px",
        height: theme.headerHeight,
        borderBottom: `1px solid ${theme.palette.divider}`,
      })}
    >
      <Box sx={{ display: "flex", alignItems: "center" }}>
        <Box sx={{ marginTop: "5px", marginRight: "6px", marginLeft: "10px" }}>
          <ViseronLogo width={40} height={40} />
        </Box>
        <Box sx={{ display: "flex", alignItems: "baseline", position: "relative" }}>
          <Typography
            variant="h5"
            sx={{
              paddingRight: "50px",
            }}
          >
            Viseron
          </Typography>
          {version && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                fontSize: "0.6rem",
                position: "absolute",
                top: 0,
                right: "30px",
              }}
            >
              {version}
            </Typography>
          )}
        </Box>
      </Box>
    </Container>
  );
}

function getItem(index: number, location: Location, item: DrawerItemTypes) {
  switch (item.type) {
    case "header":
      return (
        <ListSubheader key={index} sx={{ background: "transparent" }}>
          {item.title}
        </ListSubheader>
      );
    case "link":
      if (item.external) {
        return (
          <ListItemButton
            key={index}
            component="a"
            href={item.path}
            target="_blank"
            rel="noopener"
          >
            <ListItemIcon sx={{ minWidth: 40 }}>
              <item.icon size={23} />
            </ListItemIcon>
            <ListItemText primary={item.title} />
          </ListItemButton>
        );
      }
      return (
        <ListItemButton
          key={index}
          component={Link}
          to={item.path}
          selected={item.path === location.pathname}
        >
          <ListItemIcon sx={{ minWidth: 40 }}>
            <item.icon size={23} />
          </ListItemIcon>
          <ListItemText primary={item.title} />
        </ListItemButton>
      );
    case "divider":
      return <Divider key={index} />;
    default:
      return null;
  }
}

export default function AppDrawer({
  drawerOpen,
  setDrawerOpen,
}: AppDrawerProps) {
  const { auth, user } = useAuthContext();
  const location = useLocation();

  const drawerItems = getDrawerItems(auth, user);

  return (
    <Drawer
      anchor="left"
      open={drawerOpen}
      onClose={() => setDrawerOpen(false)}
      color="primary"
      ModalProps={{
        keepMounted: true,
      }}
      sx={{
        '& .MuiDrawer-paper': {
          borderTop: 'none !important',
          borderBottom: 'none !important',
        },
      }}
    >
      <AppDrawerHeader />
      <List>
        <Box onClick={() => setDrawerOpen(false)}>
          {drawerItems.map((item, index) => getItem(index, location, item))}
        </Box>
      </List>
    </Drawer>
  );
}
