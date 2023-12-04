import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useContext, useReducer } from "react";
import { Navigate } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

import { TextFieldItem, TextFieldItemState } from "components/TextFieldItem";
import { AuthContext } from "context/AuthContext";
import { useTitle } from "hooks/UseTitle";
import queryClient from "lib/api/client";
import { useOnboarding } from "lib/api/onboarding";

type InputState = {
  displayName: TextFieldItemState;
  username: TextFieldItemState;
  password: TextFieldItemState;
  confirmPassword: TextFieldItemState;
};

type InputAction = {
  type: keyof InputState;
  value: string;
};

const initialState: InputState = {
  displayName: { label: "Display Name", value: "", error: null },
  username: { label: "Username", value: "", error: null },
  password: { label: "Password", value: "", error: null },
  confirmPassword: { label: "Confirm Password", value: "", error: null },
};

function reducer(state: InputState, action: InputAction): InputState {
  let error = null;
  if (action.type === "confirmPassword") {
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

const Onboarding = () => {
  useTitle("Onboarding");
  const { auth } = useContext(AuthContext);

  const [inputState, dispatch] = useReducer(reducer, initialState);
  const onboarding = useOnboarding();

  if ((auth.enabled && auth.onboarding_complete) || !auth.enabled) {
    return <Navigate to="/" />;
  }

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
              <TextFieldItem<keyof InputState>
                autoFocus
                inputKind={"displayName"}
                inputState={inputState}
                dispatch={dispatch}
              />
              <TextFieldItem<keyof InputState>
                inputKind={"username"}
                inputState={inputState}
                dispatch={dispatch}
                value={inputState.username.value}
                onFocus={() => {
                  if (!inputState.username.value) {
                    dispatch({
                      type: "username",
                      value: inputState.displayName.value.toLowerCase(),
                    });
                  }
                }}
              />
              <TextFieldItem<keyof InputState>
                inputKind={"password"}
                inputState={inputState}
                dispatch={dispatch}
                password
              />
              <TextFieldItem<keyof InputState>
                inputKind={"confirmPassword"}
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
                    onboarding.mutate(
                      {
                        name: inputState.displayName.value,
                        username: inputState.username.value,
                        password: inputState.password.value,
                      },
                      {
                        onSuccess: async (_data, _variables, _context) => {
                          // Invalidate auth query to force a re-fetch, which will redirect to the dashboard
                          await queryClient.invalidateQueries(["auth"]);
                        },
                      },
                    );
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
