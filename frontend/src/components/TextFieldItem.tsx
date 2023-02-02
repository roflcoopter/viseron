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
  const [showPassword, setShowPassword] = useState(false);
  const togglePasswordVisibility = () => {
    setShowPassword((prev) => !prev);
  };
  const defaultProps = {
    fullWidth: true,
    autoComplete: "off",
    // eslint-disable-next-line no-nested-ternary
    type: props.password ? (showPassword ? "text" : "password") : "text",
    label: props.inputState[props.inputKind].label,
    helperText: props.inputState[props.inputKind].error
      ? props.inputState[props.inputKind].error
      : " ",
    error: !!props.inputState[props.inputKind].error,
    onChange: (
      event: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>
    ) =>
      props.dispatch({
        type: props.inputKind,
        value: event.target.value,
      }),
    InputProps: props.password
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

  props = { ...defaultProps, ...props };
  const { inputKind, inputState, dispatch, password, ...forwardedProps } =
    props;

  return (
    <Grid item xs={12}>
      <TextField {...forwardedProps} />
    </Grid>
  );
}
