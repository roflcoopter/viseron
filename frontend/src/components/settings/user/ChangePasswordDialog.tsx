import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";
import { useReducer } from "react";

import { useAuthAdminChangePassword } from "lib/api/auth";
import * as types from "lib/types";

interface ChangePasswordDialogProps {
  user: types.AuthUserResponse;
  onClose: () => void;
}

type InputState = {
  newPassword: { value: string; error: string | null };
  confirmPassword: { value: string; error: string | null };
};

type InputAction = {
  type: keyof InputState;
  value: string;
};

const initialState: InputState = {
  newPassword: { value: "", error: null },
  confirmPassword: { value: "", error: null },
};

function reducer(state: InputState, action: InputAction): InputState {
  let error = null;
  if (action.type === "confirmPassword") {
    if (state.newPassword.value !== action.value) {
      error = "Passwords do not match.";
    }
  }

  if (!action.value) {
    error = "Required.";
  }

  return {
    ...state,
    [action.type]: { value: action.value, error },
  };
}

const ChangePasswordDialog: React.FC<ChangePasswordDialogProps> = ({
  user,
  onClose,
}) => {
  const [inputState, dispatch] = useReducer(reducer, initialState);
  const authChangePassword = useAuthAdminChangePassword();

  const handleChangePassword = () => {
    if (inputState.newPassword.error || inputState.confirmPassword.error) {
      return;
    }

    authChangePassword.mutate(
      { user, newPassword: inputState.newPassword.value },
      {
        onSuccess: () => {
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>Change Password</DialogTitle>
      <DialogContent>
        <TextField
          margin="dense"
          label="New Password"
          type="password"
          fullWidth
          value={inputState.newPassword.value}
          onChange={(e) =>
            dispatch({ type: "newPassword", value: e.target.value })
          }
          error={!!inputState.newPassword.error}
          helperText={inputState.newPassword.error}
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
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleChangePassword}
          variant="contained"
          disabled={
            !inputState.newPassword.value ||
            !inputState.confirmPassword.value ||
            !!inputState.newPassword.error ||
            !!inputState.confirmPassword.error ||
            authChangePassword.isPending
          }
        >
          Change
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ChangePasswordDialog;
