import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Paper from "@mui/material/Paper";
import TextField, { TextFieldProps } from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useReducer, useState } from "react";
import { ReactComponent as ViseronLogo } from "viseron-logo.svg";

import { useTitle } from "hooks/UseTitle";
import { useOnboarding } from "lib/api/onboarding";

interface InputStateValues {
  label: string;
  value: string;
  error: string | null;
}

interface InputState {
  displayName: InputStateValues;
  username: InputStateValues;
  password: InputStateValues;
  confirmPassword: InputStateValues;
}

enum InputKind {
  displayName = "displayName",
  username = "username",
  password = "password",
  confirmPassword = "confirmPassword",
}

interface InputAction {
  type: InputKind;
  value: string;
}

const initialState = {
  displayName: { label: "Display Name", value: "", error: null },
  username: { label: "Username", value: "", error: null },
  password: { label: "Password", value: "", error: null },
  confirmPassword: { label: "Confirm Password", value: "", error: null },
};

function reducer(state: InputState, action: InputAction): InputState {
  let error = null;
  if (action.type === InputKind.confirmPassword) {
    if (state.password.value !== action.value) {
      error = "Passwords do not match.";
    }
  }

  if (!action.value) {
    error = "Required.";
  }

  return {
    ...state,
    [action.type]: { ...state[action.type], value: action.value, error },
  };
}

type TextFieldItemProps = TextFieldProps & {
  inputKind: InputKind;
  inputState: InputState;
  dispatch: React.Dispatch<InputAction>;
  password?: boolean;
};

const TextFieldItem = (props: TextFieldItemProps) => {
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
};

const Onboarding = () => {
  useTitle("Onboarding");
  const [inputState, dispatch] = useReducer(reducer, initialState);

  const onboarding = useOnboarding();
  // console.log(onboarding.error?.response?.data);

  return (
    <Container sx={{ marginTop: "2%" }}>
      <Box display="flex" justifyContent="center" alignItems="center">
        <ViseronLogo width={150} height={150} />
      </Box>
      <Typography variant="h4" align="center">
        Welcome to Viseron!
      </Typography>
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        sx={{ marginTop: "20px" }}
      >
        <Paper
          sx={{
            paddingTop: "5px",
            width: "95%",
            maxWidth: 400,
          }}
        >
          <Typography variant="h6" align="center" sx={{ padding: "10px" }}>
            Create an Account
          </Typography>
          {onboarding.isError ? (
            <Typography variant="h6" align="center" color="error">
              {onboarding.error?.response?.data.error}
            </Typography>
          ) : null}
          <form>
            <Grid container spacing={3} sx={{ padding: "15px" }}>
              <TextFieldItem
                autoFocus
                inputKind={InputKind.displayName}
                inputState={inputState}
                dispatch={dispatch}
              />
              <TextFieldItem
                inputKind={InputKind.username}
                inputState={inputState}
                dispatch={dispatch}
                value={inputState.username.value}
                onFocus={() => {
                  if (!inputState.username.value) {
                    dispatch({
                      type: InputKind.username,
                      value: inputState.displayName.value.toLowerCase(),
                    });
                  }
                }}
              />
              <TextFieldItem
                inputKind={InputKind.password}
                inputState={inputState}
                dispatch={dispatch}
                password
              />
              <TextFieldItem
                inputKind={InputKind.confirmPassword}
                inputState={inputState}
                dispatch={dispatch}
                password
              />
              <Grid item xs={12}>
                <Button
                  fullWidth
                  variant="contained"
                  disabled={
                    !inputState.username.value ||
                    !inputState.password.value ||
                    !inputState.confirmPassword.value ||
                    inputState.password.value !==
                      inputState.confirmPassword.value ||
                    !!inputState.username.error ||
                    !!inputState.password.error ||
                    !!inputState.confirmPassword.error ||
                    onboarding.isLoading
                  }
                  onClick={() => {
                    onboarding.mutate({
                      name: inputState.displayName.value,
                      username: inputState.username.value,
                      password: inputState.password.value,
                    });
                  }}
                >
                  Sign Up
                </Button>
              </Grid>
            </Grid>
          </form>
        </Paper>
      </Box>
    </Container>
  );
};

export default Onboarding;
