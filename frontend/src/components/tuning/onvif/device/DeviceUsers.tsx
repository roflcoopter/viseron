import {
  AddAlt,
  CustomerService,
  Help,
  TrashCan,
  User,
  UserAdmin,
  UserSimulation,
  View,
  ViewOff,
} from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Select,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { MouseEvent, useState } from "react";

import { useToast } from "hooks/UseToast";
import {
  useCreateDeviceUsers,
  useDeleteDeviceUsers,
  useGetDeviceUsers,
  useSetDeviceUsers,
} from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

const USER_LEVELS = [
  "Administrator",
  "Operator",
  "User",
  "Anonymous",
  "Extended",
] as const;
type UserLevel = (typeof USER_LEVELS)[number];

interface DeviceUsersProps {
  cameraIdentifier: string;
  deviceCapabilities?: any;
}

export function DeviceUsers({
  cameraIdentifier,
  deviceCapabilities,
}: DeviceUsersProps) {
  // Check if user configuration is not supported
  const isUserConfigNotSupported =
    deviceCapabilities?.System?.UserConfigNotSupported === true;

  const TITLE = "Users Management";
  const DESC =
    "Manage ONVIF users and their access levels. The user used on this ONVIF connection should not be changed here.";

  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } = useGetDeviceUsers(
    cameraIdentifier,
    !isUserConfigNotSupported,
  );
  const createUsersMutation = useCreateDeviceUsers(cameraIdentifier);
  const deleteUserMutation = useDeleteDeviceUsers(cameraIdentifier);
  const setUsersMutation = useSetDeviceUsers(cameraIdentifier);

  const users = data?.users;

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"add" | "edit">("add");
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [newUserLevel, setNewUserLevel] = useState<UserLevel>("User");

  // Context menu
  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    username: string;
  } | null>(null);

  const handleContextMenu = (
    event: MouseEvent<HTMLButtonElement>,
    username: string,
  ) => {
    event.preventDefault();
    setContextMenu({
      mouseX: event.clientX,
      mouseY: event.clientY,
      username,
    });
  };

  const handleContextMenuClose = () => {
    setContextMenu(null);
  };

  // Handlers
  const handleAddUser = () => {
    setDialogMode("add");
    setDialogOpen(true);
  };

  const handleEditUser = (username: string, userLevel: UserLevel) => {
    setDialogMode("edit");
    setNewUsername(username);
    setNewUserLevel(userLevel);
    setNewPassword("");
    setConfirmPassword("");
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setConfirmPassword("");
    setShowPassword(false);
    setNewUsername("");
    setNewPassword("");
    setNewUserLevel("User");
  };

  const handleCreateUser = () => {
    if (newUsername && newPassword) {
      createUsersMutation.mutate(
        [
          {
            Username: newUsername,
            Password: newPassword,
            UserLevel: newUserLevel,
          },
        ],
        {
          onSuccess: () => {
            toast.success(`User "${newUsername}" created successfully`);
            handleDialogClose();
          },
          onError: (err) => {
            toast.error(err?.message || "Failed to create user");
          },
        },
      );
    }
  };

  const handleDeleteUser = (username: string) => {
    deleteUserMutation.mutate(username, {
      onSuccess: () => {
        toast.success(`User "${username}" removed successfully`);
        handleDialogClose();
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to remove user");
      },
    });
  };

  const handleUpdateUser = () => {
    setUsersMutation.mutate(
      [
        {
          Username: newUsername,
          Password: newPassword,
          UserLevel: newUserLevel,
        },
      ],
      {
        onSuccess: () => {
          toast.success(`User "${newUsername}" updated successfully`);
          handleDialogClose();
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to update user");
        },
      },
    );
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device users"}
      isWarning={isUserConfigNotSupported}
      warningMessage="User configuration is not supported by this device"
      isEmpty={users === undefined || users.length === 0}
      title={TITLE}
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">{TITLE}</Typography>
            <Tooltip title={DESC} arrow placement="top">
              <Help size={16} />
            </Tooltip>
          </Box>
          <Button
            size="small"
            startIcon={<AddAlt size={16} />}
            onClick={handleAddUser}
            disabled={isUserConfigNotSupported}
          >
            Add
          </Button>
        </Box>

        {/* Users List */}
        {users && users.length > 0 ? (
          <Box display="flex" flexDirection="column" gap={1}>
            {users.map((user) => (
              <Button
                key={user.Username}
                variant="outlined"
                fullWidth
                onContextMenu={(e) => handleContextMenu(e, user.Username)}
                onClick={() =>
                  handleEditUser(user.Username, user.UserLevel as UserLevel)
                }
                color={
                  user.UserLevel === "Administrator"
                    ? "success"
                    : user.UserLevel === "User"
                      ? "warning"
                      : user.UserLevel === "Operator"
                        ? "info"
                        : "error"
                }
                sx={{
                  p: 1.5,
                  display: "flex",
                  justifyContent: "flex-start",
                  textTransform: "none",
                }}
              >
                {user.UserLevel === "Administrator" ? (
                  <UserAdmin style={{ marginRight: 8, flexShrink: 0 }} />
                ) : user.UserLevel === "Operator" ? (
                  <CustomerService style={{ marginRight: 8, flexShrink: 0 }} />
                ) : user.UserLevel === "User" ? (
                  <User style={{ marginRight: 8, flexShrink: 0 }} />
                ) : (
                  <UserSimulation style={{ marginRight: 8, flexShrink: 0 }} />
                )}
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 500,
                    flexGrow: 1,
                    textAlign: "left",
                  }}
                >
                  {user.Username}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ flexShrink: 0 }}
                >
                  {user.UserLevel}
                </Typography>
              </Button>
            ))}
          </Box>
        ) : (
          <Typography
            variant="caption"
            color="text.secondary"
            display="block"
            sx={{ ml: 1 }}
          >
            No users configured
          </Typography>
        )}

        {/* Context Menu */}
        <Menu
          open={contextMenu !== null}
          onClose={handleContextMenuClose}
          anchorReference="anchorPosition"
          anchorPosition={
            contextMenu !== null
              ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
              : undefined
          }
        >
          <MenuItem
            onClick={() => {
              if (contextMenu) {
                handleDeleteUser(contextMenu.username);
              }
              handleContextMenuClose();
            }}
            disabled={isUserConfigNotSupported}
            sx={{ color: "error.main" }}
          >
            <ListItemIcon sx={{ color: "error.main" }}>
              <TrashCan />
            </ListItemIcon>
            <ListItemText>Delete</ListItemText>
          </MenuItem>
        </Menu>

        {/* Add/Edit User Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              gap={1}
            >
              <Typography variant="inherit">
                {dialogMode === "add" ? "Add User" : "Edit User"}
              </Typography>
              {deviceCapabilities?.Security?.MaxUsers &&
                dialogMode === "add" && (
                  <Typography
                    variant="caption"
                    fontWeight="medium"
                    color="primary"
                  >
                    {`Max Users: ${deviceCapabilities.Security.MaxUsers}`}
                  </Typography>
                )}
            </Box>
          </DialogTitle>
          <DialogContent>
            <TextField
              autoFocus
              margin="dense"
              label="Username"
              fullWidth
              variant="outlined"
              value={newUsername}
              disabled={dialogMode === "edit"}
              onChange={(e) => setNewUsername(e.target.value)}
              slotProps={{
                htmlInput: {
                  maxLength:
                    deviceCapabilities?.Security?.MaxUserNameLength ??
                    undefined,
                },
              }}
              helperText={
                dialogMode === "add"
                  ? deviceCapabilities?.Security?.MaxUserNameLength
                    ? `Max ${deviceCapabilities.Security.MaxUserNameLength} characters`
                    : undefined
                  : undefined
              }
            />
            <TextField
              margin="dense"
              label="Password"
              type={showPassword ? "text" : "password"}
              fullWidth
              variant="outlined"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              slotProps={{
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword(!showPassword)}
                        edge="end"
                        size="small"
                      >
                        {showPassword ? (
                          <ViewOff size={20} />
                        ) : (
                          <View size={20} />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                },
                htmlInput: {
                  maxLength:
                    deviceCapabilities?.Security?.MaxPasswordLength ??
                    undefined,
                },
              }}
              helperText={
                dialogMode === "edit"
                  ? `Leave blank to keep current password.${deviceCapabilities?.Security?.MaxPasswordLength ? ` Max ${deviceCapabilities.Security.MaxPasswordLength} characters.` : ""}`
                  : deviceCapabilities?.Security?.MaxPasswordLength
                    ? `Max ${deviceCapabilities.Security.MaxPasswordLength} characters`
                    : undefined
              }
            />
            <TextField
              margin="dense"
              label="Confirm Password"
              type={showPassword ? "text" : "password"}
              fullWidth
              variant="outlined"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              error={confirmPassword !== "" && newPassword !== confirmPassword}
              slotProps={{
                htmlInput: {
                  maxLength:
                    deviceCapabilities?.Security?.MaxPasswordLength ??
                    undefined,
                },
              }}
              helperText={
                confirmPassword !== "" && newPassword !== confirmPassword
                  ? "Passwords do not match"
                  : ""
              }
            />
            {/* User Type */}
            <FormControl fullWidth margin="dense">
              <InputLabel>User Level</InputLabel>
              <Select
                value={newUserLevel}
                label="User Level"
                onChange={(e) => setNewUserLevel(e.target.value as UserLevel)}
              >
                {USER_LEVELS.map((level) => (
                  <MenuItem key={level} value={level}>
                    {level}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            {dialogMode === "add" && (
              <Button
                onClick={handleCreateUser}
                variant="contained"
                disabled={
                  !newUsername ||
                  !newPassword ||
                  !confirmPassword ||
                  newPassword !== confirmPassword ||
                  createUsersMutation.isPending
                }
              >
                {createUsersMutation.isPending ? (
                  <CircularProgress enableTrackSlot size={24} />
                ) : (
                  "Add"
                )}
              </Button>
            )}
            {dialogMode === "edit" && (
              <>
                <Button
                  onClick={() => handleDeleteUser(newUsername)}
                  color="error"
                  disabled={
                    deleteUserMutation.isPending ||
                    createUsersMutation.isPending
                  }
                >
                  {deleteUserMutation.isPending ? (
                    <CircularProgress enableTrackSlot size={24} />
                  ) : (
                    "Delete"
                  )}
                </Button>
                <Button
                  onClick={handleUpdateUser}
                  variant="contained"
                  disabled={
                    newPassword !== confirmPassword ||
                    setUsersMutation.isPending ||
                    deleteUserMutation.isPending
                  }
                >
                  {setUsersMutation.isPending ? (
                    <CircularProgress enableTrackSlot size={24} />
                  ) : (
                    "Save"
                  )}
                </Button>
              </>
            )}
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
