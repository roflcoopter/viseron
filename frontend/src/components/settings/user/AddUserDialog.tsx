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

import { useUserForm } from "hooks/UseUserForm";
import { useAuthCreate } from "lib/api/auth";
import * as types from "lib/types";

interface AddUserDialogProps {
  onClose: () => void;
}

function AddUserDialog({ onClose }: AddUserDialogProps) {
  const { inputState, dispatch, isFormValid } = useUserForm(true);
  const authCreate = useAuthCreate();

  const handleAddUser = () => {
    if (!isFormValid()) {
      return;
    }

    authCreate.mutate(
      {
        name: inputState.displayName.value,
        username: inputState.username.value,
        password: inputState.password.value,
        role: inputState.role.value as types.AuthUserResponse["role"],
      },
      {
        onSuccess: () => {
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Add User</DialogTitle>
      <DialogContent>
        <TextField
          margin="dense"
          label="Display Name"
          fullWidth
          value={inputState.displayName.value}
          onChange={(e) =>
            dispatch({ type: "displayName", value: e.target.value })
          }
          error={!!inputState.displayName.error}
          helperText={inputState.displayName.error}
        />
        <TextField
          margin="dense"
          label="Username"
          fullWidth
          value={inputState.username.value}
          onChange={(e) =>
            dispatch({ type: "username", value: e.target.value })
          }
          error={!!inputState.username.error}
          helperText={inputState.username.error}
        />
        <TextField
          margin="dense"
          label="Password"
          type="password"
          fullWidth
          value={inputState.password.value}
          onChange={(e) =>
            dispatch({ type: "password", value: e.target.value })
          }
          error={!!inputState.password.error}
          helperText={inputState.password.error}
        />
        <TextField
          margin="dense"
          label="Confirm Password"
          type="password"
          fullWidth
          value={inputState.confirmPassword.value}
          onChange={(e) =>
            dispatch({ type: "confirmPassword", value: e.target.value })
          }
          error={!!inputState.confirmPassword.error}
          helperText={inputState.confirmPassword.error}
        />
        <FormControl fullWidth margin="dense">
          <InputLabel>Role</InputLabel>
          <Select
            label="Role"
            value={inputState.role?.value || ""}
            onChange={(e) => dispatch({ type: "role", value: e.target.value })}
          >
            <MenuItem value="admin">Admin</MenuItem>
            <MenuItem value="write">Write</MenuItem>
            <MenuItem value="read">Read</MenuItem>
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleAddUser}
          variant="contained"
          disabled={!isFormValid() || authCreate.isPending}
        >
          Add
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default AddUserDialog;
