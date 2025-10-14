import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";
import Grid from "@mui/material/Grid";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import TextField, { TextFieldProps } from "@mui/material/TextField";
import { useState } from "react";

export type TextFieldItemState = {
  label: string;
  value: string;
  error: string | null;
};

type TextFieldItemProps<T extends string = string> = TextFieldProps & {
  inputKind: T;
  inputState: Record<T, TextFieldItemState>;
  dispatch: React.Dispatch<{
    type: T;
    value: string;
  }>;
  password?: boolean;
};

export function TextFieldItem<T extends string>(props: TextFieldItemProps<T>) {
  const { inputKind, inputState, dispatch, password, ...strippedProps } = props;
  const [showPassword, setShowPassword] = useState(false);
  const togglePasswordVisibility = () => {
    setShowPassword((prev) => !prev);
  };
  const defaultProps = {
    fullWidth: true,
    autoComplete: "off",
    type: password ? (showPassword ? "text" : "password") : "text",
    label: inputState[inputKind].label,
    helperText: inputState[inputKind].error ? inputState[inputKind].error : " ",
    error: !!inputState[inputKind].error,
    onChange: (
      event: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>,
    ) =>
      dispatch({
        type: inputKind,
        value: event.target.value,
      }),
    InputProps: password
      ? {
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                aria-label="toggle password visibility"
                onClick={togglePasswordVisibility}
              >
                {showPassword ? <Visibility /> : <VisibilityOff />}
              </IconButton>
            </InputAdornment>
          ),
        }
      : undefined,
  };

  const forwardedProps = { ...defaultProps, ...strippedProps };

  return (
    <Grid size={12}>
      <TextField {...forwardedProps} />
    </Grid>
  );
}
