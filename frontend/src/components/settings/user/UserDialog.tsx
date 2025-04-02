import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from "@mui/material";
import Cookies from "js-cookie";
import { useState } from "react";

import ChangePasswordDialog from "components/settings/user/ChangePasswordDialog";
import { useAuthDelete, useAuthUpdateUser, useAuthUser } from "lib/api/auth";
import * as types from "lib/types";

interface UserDialogProps {
  user: types.AuthUserResponse;
  onClose: () => void;
}

const UserDialog: React.FC<UserDialogProps> = ({ user, onClose }) => {
  const authUpdateUser = useAuthUpdateUser();
  const authDelete = useAuthDelete();
  const cookies = Cookies.get();
  const authUser = useAuthUser({
    username: cookies.user,
  });
  const [name, setName] = useState(user.name);
  const [username, setUsername] = useState(user.username);
  const [role, setRole] = useState(user.role);
  const [isChangePasswordOpen, setIsChangePasswordOpen] = useState(false);

  const handleSave = () => {
    authUpdateUser.mutate(
      { id: user.id, name, username, role },
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
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleDeleteUser}
            color="error"
            disabled={authUser.data && authUser.data.username === user.username}
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
};

export default UserDialog;
