import { SvgIconComponent } from "@mui/icons-material";
import GitHubIcon from "@mui/icons-material/GitHub";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import LiveTvIcon from "@mui/icons-material/LiveTv";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import SettingsIcon from "@mui/icons-material/Settings";
import VideoFileIcon from "@mui/icons-material/VideoFile";
import VideocamIcon from "@mui/icons-material/Videocam";
import ViewListIcon from "@mui/icons-material/ViewList";
import ViewTimelineIcon from "@mui/icons-material/ViewTimeline";
import VolunteerActivismIcon from "@mui/icons-material/VolunteerActivism";
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

import { useAuthContext } from "context/AuthContext";
import * as types from "lib/types";

type DrawerItemHeader = { type: "header"; title: string };

type DrawerItemLink = {
  type: "link";
  path: string;
  title: string;
  icon: SvgIconComponent;
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
    { type: "link", title: "Cameras", icon: VideocamIcon, path: "/" },
    {
      type: "link",
      title: "Recordings",
      icon: VideoFileIcon,
      path: "/recordings",
    },
    {
      type: "link",
      title: "Events",
      icon: ImageSearchIcon,
      path: "/events?tab=events",
    },
    {
      type: "link",
      title: "Timeline",
      icon: ViewTimelineIcon,
      path: "/events?tab=timeline",
    },
    {
      type: "link",
      title: "Live",
      icon: LiveTvIcon,
      path: "/live",
    },
    { type: "link", title: "Entities", icon: ViewListIcon, path: "/entities" },
    ...(!auth.enabled || (auth.enabled && user?.role === "admin")
      ? [
          { type: "divider" } as DrawerItemTypes,
          { type: "header", title: "Administration" } as DrawerItemTypes,
          {
            type: "link",
            title: "Settings",
            icon: SettingsIcon,
            path: "/settings",
          } as DrawerItemTypes,
        ]
      : []),
    { type: "divider" },
    { type: "header", title: "Links" },
    {
      type: "link",
      title: "GitHub",
      icon: GitHubIcon,
      path: "https://github.com/roflcoopter/viseron",
      external: true,
    },
    {
      type: "link",
      title: "Documentation",
      icon: MenuBookIcon,
      path: "https://viseron.netlify.app",
      external: true,
    },
    {
      type: "link",
      title: "Donations",
      icon: VolunteerActivismIcon,
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
  return (
    <Container
      fixed
      disableGutters
      sx={(theme) => ({
        display: "flex",
        alignItems: "center",
        justifyContent: "start",
        paddingRight: "10px",
        height: theme.headerHeight,
        borderBottom: `1px solid ${theme.palette.divider}`,
      })}
    >
      <Box sx={{ margin: "10px" }}>
        <ViseronLogo width={45} height={45} />
      </Box>
      <Typography
        variant="h5"
        sx={{
          paddingRight: "50px",
        }}
      >
        Viseron
      </Typography>
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
              <item.icon />
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
            <item.icon />
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
