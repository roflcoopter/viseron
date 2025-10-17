import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  ListItemText,
  MenuItem,
  Select,
  SelectChangeEvent,
  TextField,
} from "@mui/material";
import { useState } from "react";

import ChangePasswordDialog from "components/settings/user/ChangePasswordDialog";
import { useAuthContext } from "context/AuthContext";
import { useAuthDelete, useAuthUpdateUser } from "lib/api/auth";
import { useCamerasAll } from "lib/api/cameras";
import * as types from "lib/types";

const CAMERA_SELECT_LABEL = "Cameras - Empty gives access to all cameras";

interface UserDialogProps {
  user: types.AuthUserResponse;
  onClose: () => void;
}

function UserDialog({ user, onClose }: UserDialogProps) {
  const { user: currentUser } = useAuthContext();
  const authUpdateUser = useAuthUpdateUser();
  const authDelete = useAuthDelete();
  const camerasAll = useCamerasAll();

  const [name, setName] = useState(user.name);
  const [username, setUsername] = useState(user.username);
  const [role, setRole] = useState(user.role);
  const [assignedCameras, setAssignedCameras] = useState(
    user.assigned_cameras || [],
  );
  const [isChangePasswordOpen, setIsChangePasswordOpen] = useState(false);

  const handleSave = () => {
    authUpdateUser.mutate(
      { id: user.id, name, username, role, assigned_cameras: assignedCameras },
      {
        onSuccess: () => {
          onClose();
        },
      },
    );
  };

  const handleDeleteUser = () => {
    authDelete.mutate(user, {
      onSuccess: () => {
        onClose();
      },
    });
  };

  const handleOpenChangePassword = () => {
    setIsChangePasswordOpen(true);
  };

  const handleCloseChangePassword = () => {
    setIsChangePasswordOpen(false);
  };

  const handleCameraChange = (event: SelectChangeEvent<string[]>) => {
    if (
      event.target.value.includes("<select-all-cameras>") &&
      assignedCameras.length === Object.keys(camerasAll.combinedData).length
    ) {
      setAssignedCameras([]);
      return;
    }

    if (event.target.value.includes("<select-all-cameras>")) {
      const allCameraIds = Object.values(camerasAll.combinedData).map(
        (camera) => camera.identifier,
      );
      setAssignedCameras(allCameraIds);
      return;
    }
    setAssignedCameras(event.target.value as string[]);
  };

  return (
    <>
      <Dialog open onClose={onClose} fullWidth maxWidth="sm">
        <DialogTitle>{name}</DialogTitle>
        <DialogContent>
          <TextField
            margin="dense"
            label="Display Name"
            fullWidth
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <TextField
            margin="dense"
            label="Username"
            fullWidth
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <FormControl fullWidth margin="dense">
            <InputLabel>Role</InputLabel>
            <Select
              label="Role"
              value={role}
              onChange={(e) =>
                setRole(e.target.value as types.AuthUserResponse["role"])
              }
            >
              <MenuItem value="admin">Admin</MenuItem>
              <MenuItem value="write">Write</MenuItem>
              <MenuItem value="read">Read</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth margin="dense">
            <InputLabel>{CAMERA_SELECT_LABEL}</InputLabel>
            <Select
              multiple
              label={CAMERA_SELECT_LABEL}
              value={assignedCameras}
              onChange={handleCameraChange}
              renderValue={(selected) =>
                (selected as string[])
                  .map(
                    (cameraId) =>
                      camerasAll.combinedData[cameraId]?.name || cameraId,
                  )
                  .join(", ")
              }
            >
              <MenuItem value="<select-all-cameras>">
                <Checkbox
                  checked={
                    assignedCameras.length ===
                    Object.keys(camerasAll.combinedData).length
                  }
                />
                <ListItemText primary="Select all cameras" />
              </MenuItem>
              {Object.values(camerasAll.combinedData).map((camera) => (
                <MenuItem key={camera.identifier} value={camera.identifier}>
                  <Checkbox
                    checked={assignedCameras.includes(camera.identifier)}
                  />
                  <ListItemText primary={camera.name} />
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleDeleteUser}
            color="error"
            disabled={!!(currentUser && currentUser.username === user.username)}
          >
            Delete User
          </Button>
          <Button onClick={handleOpenChangePassword} color="primary">
            Change Password
          </Button>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSave}
            variant="contained"
            disabled={authUpdateUser.isPending}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
      {isChangePasswordOpen && (
        <ChangePasswordDialog onClose={handleCloseChangePassword} user={user} />
      )}
    </>
  );
}

export default UserDialog;
