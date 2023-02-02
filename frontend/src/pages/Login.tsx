import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useReducer } from "react";
import { useNavigate } from "react-router-dom";
import { ReactComponent as ViseronLogo } from "viseron-logo.svg";

import { TextFieldItem, TextFieldItemState } from "components/TextFieldItem";
import { useTitle } from "hooks/UseTitle";
import { useAuthLogin } from "lib/api/auth";

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
  const [inputState, dispatch] = useReducer(reducer, initialState);

  const navigate = useNavigate();
  async function onSuccessLogin() {
    navigate("/");
  }
  const login = useAuthLogin(onSuccessLogin);

  return (
    <Container sx={{ marginTop: "2%" }}>
      <Box display="flex" justifyContent="center" alignItems="center">
        <ViseronLogo width={150} height={150} />
      </Box>
      <Typography variant="h4" align="center">
        Welcome back!
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
                    login.isLoading
                  }
                  onClick={() => {
                    login.mutate({
                      username: inputState.username.value,
                      password: inputState.password.value,
                    });
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