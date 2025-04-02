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
import Cookies from "js-cookie";
import { Link } from "react-router-dom";

import { Loading } from "components/loading/Loading";
import { useAuthContext } from "context/AuthContext";
import { useHideScrollbar } from "hooks/UseHideScrollbar";
import { useTitle } from "hooks/UseTitle";
import { useAuthUser } from "lib/api/auth";

const Settings = () => {
  useTitle("Settings");
  useHideScrollbar();

  const { auth } = useAuthContext();
  const userQuery = useAuthUser({
    username: Cookies.get().user,
    configOptions: { enabled: auth.enabled && !!Cookies.get().user },
  });

  const settingsMenuItems = [
    {
      name: "Configuration",
      description: "Edit the YAML configuration",
      path: "/settings/configuration",
      icon: <SettingsIcon />,
      color: "blue",
      disabled: false,
    },
    {
      name: "User Management",
      description: "Create, edit, and delete users",
      path: "/settings/users",
      icon: <PeopleIcon />,
      color: "green",
      disabled: !auth.enabled || userQuery.data?.role !== "admin",
    },
    {
      name: "Logs",
      description: "View system logs, not implemented yet",
      path: "/settings/logs",
      icon: <ArticleIcon />,
      color: "orange",
      disabled: true,
    },
  ];

  if (userQuery.isLoading) {
    return <Loading text="Loading Settings" />;
  }

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
                    secondary={item.description}
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
