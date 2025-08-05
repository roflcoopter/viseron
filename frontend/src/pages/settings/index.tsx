import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";
import ArticleIcon from "@mui/icons-material/Article";
import PeopleIcon from "@mui/icons-material/People";
import SettingsIcon from "@mui/icons-material/Settings";
import { ListItemButton } from "@mui/material";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Container from "@mui/material/Container";
import List from "@mui/material/List";
import ListItemAvatar from "@mui/material/ListItemAvatar";
import ListItemText from "@mui/material/ListItemText";
import { Link } from "react-router-dom";

import { useAuthContext } from "context/AuthContext";
import { useHideScrollbar } from "hooks/UseHideScrollbar";
import { useTitle } from "hooks/UseTitle";

const Settings = () => {
  useTitle("Settings");
  useHideScrollbar();

  const { auth, user } = useAuthContext();

  const settingsMenuItems = [
    {
      name: "Configuration",
      description: "Edit the YAML configuration",
      path: "/settings/configuration",
      icon: <SettingsIcon />,
      color: "blue",
      disabled: false,
      disabledReason: null,
    },
    {
      name: "User Management",
      description: "Create, edit, and delete users",
      path: "/settings/users",
      icon: <PeopleIcon />,
      color: "green",
      disabled: !auth.enabled || user?.role !== "admin",
      disabledReason: !auth.enabled
        ? "Enable authentication to manage users"
        : "Only admins can manage users",
    },
    {
      name: "System Events",
      description: "View system events dispatched by the server",
      path: "/settings/system-events",
      icon: <ArticleIcon />,
      color: "purple",
      disabled: false,
      disabledReason: null,
    },
    {
      name: "Logs",
      description: "View system logs",
      path: "/settings/logs",
      icon: <ArticleIcon />,
      color: "orange",
      disabled: true,
      disabledReason: "Not implemented yet",
    },
  ];

  return (
    <Container maxWidth={false}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "80vh",
        }}
      >
        <Card sx={{ maxWidth: 600, width: "100%" }}>
          <CardContent>
            <List sx={{ width: "100%", maxWidth: 600 }}>
              {settingsMenuItems.map((item) => (
                <ListItemButton
                  disabled={item.disabled}
                  key={item.path}
                  component={Link}
                  to={item.path}
                  sx={{
                    "&:hover": {
                      bgcolor: "action.hover",
                    },
                  }}
                >
                  <ListItemAvatar>
                    <Avatar
                      sx={{
                        bgcolor: item.color,
                        color: "primary.contrastText",
                      }}
                    >
                      {item.icon}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={item.name}
                    secondary={
                      item.disabled
                        ? `${item.description}. ${item.disabledReason}`
                        : item.description
                    }
                  />
                  <ArrowForwardIosIcon fontSize="small" />
                </ListItemButton>
              ))}
            </List>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default Settings;
