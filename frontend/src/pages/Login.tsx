import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import Stack from "@mui/material/Stack";
import { useEffect, useReducer, useRef } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTheme } from "@mui/material/styles";
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

function Login() {
  useTitle("Login");
  const theme = useTheme();
  const { auth } = useAuthContext();
  const location = useLocation();
  const navigate = useNavigate();
  const login = useAuthLogin();

  const [inputState, dispatch] = useReducer(reducer, initialState);
  const fromRef = useRef(undefined);

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
    <Box
      sx={{
        minHeight: "90vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        py: 2,
        px: 2
      }}
    >
      <Container maxWidth="sm">
        <Stack spacing={4} alignItems="center">
          {/* Logo and Brand Section */}
          <Box
            sx={{
              textAlign: "center",
              mb: 2
            }}
          >
            <Box
              sx={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                width: 150,
                height: 150,
                margin: "0 auto",
                "& > *": {
                  animation: "viseron-slow-spin 30s linear infinite",
                  transformOrigin: "center center",
                  display: "block",
                },
                "@keyframes viseron-slow-spin": {
                  "0%": { transform: "rotate(0deg)" },
                  "100%": { transform: "rotate(360deg)" },
                },
              }}
            >
              <ViseronLogo width={150} height={150} />
            </Box>
            <Typography 
              variant="h4" 
              sx={{ 
                color: 'text.primary',
              }}
            >
              Viseron Login
            </Typography>
          </Box>

          {/* Login Form */}
          <Paper
            elevation={8}
            sx={{
              width: "100%",
              maxWidth: 400,
              borderRadius: 2,
              overflow: "hidden",
              border: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Box sx={{ p: 4 }}>

              {login.error && (
                <Box
                  sx={{
                    p: 2,
                    mb: 3,
                    borderRadius: 2,
                    backgroundColor: `${theme.palette.error.main}10`,
                    border: `1px solid ${theme.palette.error.main}30`,
                  }}
                >
                  <Typography 
                    variant="body2" 
                    align="center" 
                    sx={{ 
                      color: 'error.main',
                      fontWeight: 500
                    }}
                  >
                    {login.error.response && login.error.response.data.status === 401
                      ? "Incorrect username or password"
                      : "An error occurred. Please try again."}
                  </Typography>
                </Box>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                }}
              >
                <Stack spacing={3}>
                  <TextFieldItem<keyof InputState>
                    inputKind="username"
                    inputState={inputState}
                    dispatch={dispatch}
                    value={inputState.username.value}
                  />
                  <TextFieldItem<keyof InputState>
                    inputKind="password"
                    inputState={inputState}
                    dispatch={dispatch}
                    password
                  />
                  
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    size="large"
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
                    sx={{
                      py: 1.5,
                      borderRadius: 2,
                      textTransform: "none",
                      fontSize: "1rem",
                      fontWeight: 600,
                      mt: 2,
                      boxShadow: 2,
                      '&:hover': {
                        boxShadow: 4,
                      },
                      '&:disabled': {
                        boxShadow: 0,
                      }
                    }}
                  >
                    {login.isPending ? "SIGNING IN..." : "SIGN IN"}
                  </Button>
                </Stack>
              </form>
            </Box>
          </Paper>
        </Stack>
      </Container>
    </Box>
  );
}

export default Login;