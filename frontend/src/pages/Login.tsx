import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useEffect, useReducer, useRef } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

import { TextFieldItem, TextFieldItemState } from "components/TextFieldItem";
import { useAuthContext } from "context/AuthContext";
import { useTitle } from "hooks/UseTitle";
import { useAuthLogin } from "lib/api/auth";
import queryClient from "lib/api/client";

type InputState = {
  username: TextFieldItemState;
  password: TextFieldItemState;
};

type InputAction = {
  type: keyof InputState;
  value: string;
};

const initialState: InputState = {
  username: { label: "Username", value: "", error: null },
  password: { label: "Password", value: "", error: null },
};

function reducer(state: InputState, action: InputAction): InputState {
  let error = null;
  if (!action.value) {
    error = "Required.";
  }

  return {
    ...state,
    [action.type]: { ...state[action.type], value: action.value, error },
  };
}

const Login = () => {
  useTitle("Login");
  const { auth } = useAuthContext();
  const location = useLocation();
  const navigate = useNavigate();
  const login = useAuthLogin();

  const [inputState, dispatch] = useReducer(reducer, initialState);
  const fromRef = useRef();

  queryClient.removeQueries({
    predicate(query) {
      return query.queryKey[0] !== "auth" && query.queryKey[1] !== "enabled";
    },
  });
  queryClient.invalidateQueries({
    refetchType: "none",
    predicate(query) {
      return query.queryKey[0] !== "auth" && query.queryKey[1] !== "enabled";
    },
  });

  useEffect(() => {
    fromRef.current =
      location.state && location.state.from ? location.state.from : null;
    // Clear the state parameter
    if (fromRef.current) {
      navigate(location.pathname, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (auth.enabled && !auth.onboarding_complete) {
    return <Navigate to="/onboarding" />;
  }

  if (!auth.enabled) {
    return <Navigate to="/" />;
  }

  return (
    <Container sx={{ marginTop: "2%" }}>
      <Box display="flex" justifyContent="center" alignItems="center">
        <ViseronLogo width={150} height={150} />
      </Box>
      <Typography variant="h4" align="center">
        Viseron
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
            Enter your credentials
          </Typography>
          {login.error ? (
            <Typography variant="h6" align="center" color="error">
              {login.error.response && login.error.response.data.status === 401
                ? "Incorrect username or password."
                : "An error occurred."}
            </Typography>
          ) : null}
          <form>
            <Grid container spacing={3} sx={{ padding: "15px" }}>
              <TextFieldItem<keyof InputState>
                inputKind={"username"}
                inputState={inputState}
                dispatch={dispatch}
                value={inputState.username.value}
              />
              <TextFieldItem<keyof InputState>
                inputKind={"password"}
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
                    !!inputState.username.error ||
                    !!inputState.password.error ||
                    login.isPending
                  }
                  onClick={() => {
                    login.mutate(
                      {
                        username: inputState.username.value,
                        password: inputState.password.value,
                      },
                      {
                        onSuccess: async (_data, _variables, _context) => {
                          navigate(fromRef.current ? fromRef.current : "/");
                        },
                      },
                    );
                  }}
                >
                  Login
                </Button>
              </Grid>
            </Grid>
          </form>
        </Paper>
      </Box>
    </Container>
  );
};

export default Login;
